from collections.abc import Iterable
from dataclasses import dataclass

from prometheus_client import Counter, Gauge

from ..types.message_format import MessageFormat
from ..types.peer import Peer

SEND_PLAN_ELIGIBLE_PEERS = Gauge(
    "ct_send_plan_eligible_peers",
    "Eligible peers in latest send plan",
)
SEND_PLAN_STEPS = Counter(
    "ct_send_plan_steps_total",
    "Send plan steps emitted",
)


@dataclass
class SendPlanStep:
    message: MessageFormat | None
    sleep_seconds: float


class SendPlanCoordinator:
    def build_steps(
        self,
        peers: Iterable[Peer],
        minimum_delay_between_batches: float,
        sleep_mean: float,
        sleep_std: float,
    ) -> list[SendPlanStep]:
        steps: list[SendPlanStep] = []
        eligible_count = 0

        for peer in peers:
            if peer.yearly_message_count is None:
                continue

            delay = peer.message_delay
            if delay is None:
                steps.append(
                    SendPlanStep(
                        message=None,
                        sleep_seconds=peer.next_idle_sleep(sleep_mean, sleep_std),
                    )
                )
                SEND_PLAN_STEPS.inc()
                continue

            eligible_count += 1
            message = peer.build_relay_request(delay, minimum_delay_between_batches)
            steps.append(SendPlanStep(message=message, sleep_seconds=delay * message.batch_size))
            SEND_PLAN_STEPS.inc()

        SEND_PLAN_ELIGIBLE_PEERS.set(eligible_count)
        return steps
