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
    ROUND_IP_GROUPS,
    ROUND_MAX_IP_GROUP_SIZE,
    ROUND_RELAYERS,
    ROUND_RELAYERS_WITH_KNOWN_IP,
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
        Returns False if the round should be abandoned: the node stopped, or the eligible
        set outgrew the plan and a new round must be planned.
        """
        while self.running and not self._outgrew_plan(plan):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            await asyncio.sleep(min(remaining, REPLAN_CHECK_INTERVAL_SECONDS))
        if self.running:
            logger.info(
                "Abandoning burst round, eligible relayers outgrew the plan",
                {
                    "planned_relayers": plan.relayer_count,
                    "eligible_relayers": len(self.eligible_relayers),
                },
            )
        return False

    def _group_relayers_by_ip(self, relayers: list[str]) -> list[list[str]]:
        """
        Group relayers that share an announced host (IP or DNS name, not resolved) into one
        scheduling unit, so they burst together. A relayer whose host is unknown is its own
        singleton unit, preserving today's one-at-a-time behaviour for it.

        A host with more relayers than `max_concurrent_bursts_per_ct` is split into consecutive
        chunks of at most that many, so no single tick starts more than the cap's worth of bursts
        to one host; the chunks stay adjacent so the host is still hit in back-to-back waves. A
        cap of 0 means no limit and keeps the whole host in one unit. This bounds the per-wave
        burst count, not total concurrency: a wave can still overlap the previous one while its
        bursts are in flight.

        The host order and each host's members are shuffled to keep the burst order unpredictable
        to relayers.
        """
        cap = self.params.incentive.max_concurrent_bursts_per_ct

        by_host: dict[str, list[str]] = {}
        singletons: list[str] = []
        for relayer in relayers:
            peer = self.peers.get(relayer)
            host = peer.ip if peer is not None else None
            if host is None:
                singletons.append(relayer)
            else:
                by_host.setdefault(host, []).append(relayer)

        # A block is the consecutive unit(s) of one host (or a lone singleton). Shuffling blocks
        # keeps a chunked host's waves together instead of scattering them across the round.
        blocks: list[list[list[str]]] = [[[relayer]] for relayer in singletons]
        for members in by_host.values():
            if len(members) > 1:
                _secure_random.shuffle(members)
            if cap > 0 and len(members) > cap:
                chunks = [members[i : i + cap] for i in range(0, len(members), cap)]
            else:
                chunks = [members]
            blocks.append(chunks)

        _secure_random.shuffle(blocks)
        return [unit for block in blocks for unit in block]

    async def _run_round(self) -> None:
        """
        One pass over the relayers this CT node considers eligible: group those that share an
        announced host (a host larger than the concurrency cap is split into consecutive waves),
        then start a burst to each unit every `unit_step` seconds, without waiting for earlier
        bursts to finish. Every relayer in a unit is queued at the same offset so co-located
        nodes are hit simultaneously. The next round starts when this one ends, or earlier if the
        eligible set outgrew the plan.
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

        units = self._group_relayers_by_ip(relayers)
        # Spread the units (not individual relayers) across the round; same-IP relayers in a unit
        # fire together. round_duration keeps the per-relayer cadence and cost model intact.
        unit_step = plan.round_duration / len(units)

        self._log_round_start(plan)
        self._set_group_metrics(units, unit_step)

        round_start = time.monotonic()
        for index, unit in enumerate(units):
            if not await self._sleep_until(round_start + index * unit_step, plan):
                return

            for relayer in unit:
                # A relayer that became ineligible during the round is skipped for the rest of it.
                if relayer not in self.eligible_relayers:
                    BURSTS.labels(result="skipped_ineligible").inc()
                    continue

                await MessageQueue().put(MessageFormat(relayer))
                BURSTS.labels(result="queued").inc()

        await self._sleep_until(round_start + plan.round_duration, plan)

    def _set_group_metrics(self, units: list[list[str]], unit_step: float) -> None:
        known_ip = sum(
            1
            for unit in units
            for relayer in unit
            if (peer := self.peers.get(relayer)) is not None and peer.ip is not None
        )
        ROUND_IP_GROUPS.set(len(units))
        ROUND_MAX_IP_GROUP_SIZE.set(max((len(unit) for unit in units), default=0))
        ROUND_RELAYERS_WITH_KNOWN_IP.set(known_ip)
        ROUND_STEP.set(unit_step)

    @keepalive
    async def relay_messages(self):
        await self._run_round()
