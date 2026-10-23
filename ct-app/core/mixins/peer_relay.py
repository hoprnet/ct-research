import asyncio
import logging
import random
import time
from typing import Optional

from ..components.decorators import keepalive
from ..messages.message_metrics import (
    BURSTS,
    PROJECTED_MONTHLY_COST,
    ROUND_CONCURRENCY,
    ROUND_DURATION,
    ROUND_RELAYERS,
    ROUND_STEP,
)
from ..services.burst_plan import RoundPlan
from ..types.message_format import MessageFormat
from ..types.message_queue import MessageQueue
from .runtime_state import NodeRuntimeState

IDLE_NO_WORK_SLEEP_SECONDS = 1.0
# How often a sleeping round checks whether the eligible set outgrew the one it was planned with.
REPLAN_CHECK_INTERVAL_SECONDS = 60.0
# The eligible set is still filling up right after startup: a round planned from a handful of
# relayers would otherwise stay near-idle for its whole duration (round_duration = ct_node_count
# x target_relayer_interval). Replan once the set exceeds this multiple of the planned count.
REPLAN_GROWTH_FACTOR = 2

logger = logging.getLogger(__name__)

# The burst order must not be predictable by relayers.
_secure_random = random.SystemRandom()


class PeerRelayMixin(NodeRuntimeState):
    def _session_mtu(self) -> Optional[int]:
        for session in self.sessions.values():
            if session.mtu:
                return session.mtu
        return None

    def _log_round_start(self, plan: RoundPlan) -> None:
        ticket_price = self.ticket_price.value if self.ticket_price else None
        summary = plan.summary(self._session_mtu(), ticket_price)
        summary.update(self.relayed_cost_tracker.summary())
        logger.info("Starting burst round", summary)

        ROUND_RELAYERS.set(plan.relayer_count)
        ROUND_DURATION.set(plan.round_duration)
        ROUND_STEP.set(plan.step)
        ROUND_CONCURRENCY.set(plan.concurrency)
        mtu = self._session_mtu()
        if mtu and ticket_price is not None:
            PROJECTED_MONTHLY_COST.set(float(plan.max_monthly_cost(mtu, ticket_price).value))

    def _outgrew_plan(self, plan: RoundPlan) -> bool:
        return len(self.eligible_relayers) > REPLAN_GROWTH_FACTOR * plan.relayer_count

    async def _sleep_until(self, deadline: float, plan: RoundPlan) -> bool:
        """
        Sleep until `deadline`, waking up periodically to check that the plan is still valid.
        Returns False if the round should be abandoned and planned again.
        """
        while self.running and not self._outgrew_plan(plan):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(remaining, REPLAN_CHECK_INTERVAL_SECONDS))
        return False

    async def _run_round(self) -> None:
        """
        One pass over the relayers this CT node considers eligible: shuffle them, then start a
        burst to each one every `step` seconds, without waiting for earlier bursts to finish.
        The next round starts when this one ends, or earlier if the eligible set outgrew the plan.
        """
        relayers = sorted(self.eligible_relayers)
        if not relayers:
            await asyncio.sleep(IDLE_NO_WORK_SLEEP_SECONDS)
            return

        try:
            plan = RoundPlan.build(self.params.incentive, len(relayers))
        except ValueError as err:
            logger.error("Cannot plan a burst round", {"error": str(err)})
            await asyncio.sleep(IDLE_NO_WORK_SLEEP_SECONDS)
            return

        _secure_random.shuffle(relayers)
        self._log_round_start(plan)

        round_start = time.monotonic()
        for index, relayer in enumerate(relayers):
            if not await self._sleep_until(round_start + index * plan.step, plan):
                return

            # A relayer that became ineligible during the round is skipped for the rest of it.
            if relayer not in self.eligible_relayers:
                BURSTS.labels(result="skipped_ineligible").inc()
                continue

            await MessageQueue().put(MessageFormat(relayer))
            BURSTS.labels(result="queued").inc()

        await self._sleep_until(round_start + plan.round_duration, plan)

    @keepalive
    async def relay_messages(self):
        await self._run_round()
