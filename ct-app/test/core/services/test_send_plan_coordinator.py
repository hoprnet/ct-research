from core.services.send_plan_coordinator import SendPlanCoordinator
from core.types.peer import Peer


def test_build_steps_includes_eligible_peer_message_and_sleep():
    coordinator = SendPlanCoordinator()
    peer = Peer("0xpeer")
    peer.yearly_message_count = 10.0

    steps = coordinator.build_steps(
        [peer],
        minimum_delay_between_batches=2.0,
        sleep_mean=1.0,
        sleep_std=0.1,
    )

    assert len(steps) == 1
    assert steps[0].message is not None
    assert steps[0].sleep_seconds > 0


def test_build_steps_skips_ineligible_peer():
    coordinator = SendPlanCoordinator()
    peer = Peer("0xpeer")
    peer.yearly_message_count = None

    steps = coordinator.build_steps(
        [peer],
        minimum_delay_between_batches=2.0,
        sleep_mean=1.0,
        sleep_std=0.1,
    )

    assert steps == []
