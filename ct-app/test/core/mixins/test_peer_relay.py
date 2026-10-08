from types import SimpleNamespace
from typing import Any, cast

import pytest

from core.config_parser.incentive import IncentiveParams
from core.mixins import peer_relay
from core.mixins.peer_relay import PeerRelayMixin
from core.services.burst_plan import RelayedCostTracker
from test.queue_utils import drain_queue


class FakeClock:
    def __init__(self, now: float = 100.0):
        self.now = now
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class DummyRelayNode(PeerRelayMixin):
    pass


def _incentive(**overrides) -> IncentiveParams:
    values = {
        "min_outgoing_channels": 5,
        "min_channel_balance": "50 wxHOPR",
        "burst_rate": 8,
        "burst_duration": "10s",
        "target_relayer_interval": "600s",
        "max_concurrent_bursts_per_ct": 0,
        "ct_node_count": 5,
    }
    values.update(overrides)
    return IncentiveParams(values)


def _node(relayers: set[str], **overrides) -> DummyRelayNode:
    node = DummyRelayNode()
    node.eligible_relayers = set(relayers)
    node.params = cast(Any, SimpleNamespace(incentive=_incentive(**overrides)))
    node.sessions = {}
    node.ticket_price = None
    node.relayed_cost_tracker = RelayedCostTracker()
    node.running = True
    return node


async def _drain_queue() -> list[str]:
    return [message.relayer for message in await drain_queue()]


@pytest.fixture
def clock(mocker) -> FakeClock:
    clock = FakeClock()
    mocker.patch.object(peer_relay.time, "monotonic", side_effect=clock.monotonic)
    mocker.patch.object(peer_relay.asyncio, "sleep", side_effect=clock.sleep)
    return clock


@pytest.mark.asyncio
async def test_round_bursts_every_eligible_relayer_once_spaced_by_step(clock: FakeClock):
    await _drain_queue()
    relayers = {f"relayer_{i}" for i in range(4)}
    node = _node(relayers)

    await node._run_round()

    assert sorted(await _drain_queue()) == sorted(relayers)
    # T_round = 5 x 600 s = 3000 s, step = 3000 / 4 = 750 s; the round waits for its end.
    assert clock.sleeps == [750.0, 750.0, 750.0, 750.0]
    assert clock.now == pytest.approx(100.0 + 3000.0)


@pytest.mark.asyncio
async def test_round_order_is_shuffled(clock: FakeClock, mocker):
    await _drain_queue()
    shuffle = mocker.patch.object(peer_relay._secure_random, "shuffle", side_effect=list.reverse)
    node = _node({"a", "b", "c"})

    await node._run_round()

    shuffle.assert_called_once()
    assert await _drain_queue() == ["c", "b", "a"]


@pytest.mark.asyncio
async def test_round_skips_relayer_that_became_ineligible(clock: FakeClock, mocker):
    await _drain_queue()
    mocker.patch.object(peer_relay._secure_random, "shuffle", side_effect=lambda items: None)
    node = _node({"a", "b", "c"})

    original_sleep = clock.sleep

    async def sleep_and_drop(seconds: float) -> None:
        await original_sleep(seconds)
        node.eligible_relayers.discard("b")

    mocker.patch.object(peer_relay.asyncio, "sleep", side_effect=sleep_and_drop)

    await node._run_round()

    assert await _drain_queue() == ["a", "c"]


@pytest.mark.asyncio
async def test_round_does_not_add_relayers_that_joined_mid_round(clock: FakeClock, mocker):
    await _drain_queue()
    node = _node({"a"})
    original_sleep = clock.sleep

    async def sleep_and_join(seconds: float) -> None:
        await original_sleep(seconds)
        node.eligible_relayers.add("late")

    mocker.patch.object(peer_relay.asyncio, "sleep", side_effect=sleep_and_join)

    await node._run_round()

    assert await _drain_queue() == ["a"]


@pytest.mark.asyncio
async def test_round_stretches_when_concurrency_cap_applies(clock: FakeClock):
    await _drain_queue()
    # 600 relayers need 2 bursts at once; a cap of 1 stretches the round to 600 x 10 s.
    node = _node({f"r{i}" for i in range(600)}, max_concurrent_bursts_per_ct=1)

    await node._run_round()

    assert len(await _drain_queue()) == 600
    assert clock.now == pytest.approx(100.0 + 6000.0)


@pytest.mark.asyncio
async def test_round_idles_without_eligible_relayers(clock: FakeClock):
    await _drain_queue()
    node = _node(set())

    await node._run_round()

    assert clock.sleeps == [peer_relay.IDLE_NO_WORK_SLEEP_SECONDS]
    assert await _drain_queue() == []


@pytest.mark.asyncio
async def test_round_idles_on_invalid_parameters(clock: FakeClock, mocker):
    await _drain_queue()
    node = _node({"a"}, burst_duration="0s")
    logger_error = mocker.patch.object(peer_relay.logger, "error")

    await node._run_round()

    logger_error.assert_called_once()
    assert await _drain_queue() == []


@pytest.mark.asyncio
async def test_round_stops_when_node_stops(clock: FakeClock):
    await _drain_queue()
    node = _node({"a", "b"})
    node.running = False

    await node._run_round()

    assert await _drain_queue() == []
