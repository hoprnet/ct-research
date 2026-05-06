from typing import Any, cast
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.types.balance import Balance
from core.config_parser.economic_model import LegacyParams, SigmoidParams
from core.mixins.economic_system import EconomicSystemMixin


class FakeModel:
    coefficients: Any
    total_token_supply: Balance
    network_capacity: int

    def __init__(self, result: float):
        self.result = result
        self.calls: list[tuple[Any, Any, Any]] = []

    def yearly_message_count(self, stake, ticket_price, model_input):
        self.calls.append((stake, ticket_price, model_input))
        return self.result


class FakeEconomicModel:
    def __init__(self, legacy_result: float, sigmoid_result: float):
        self.legacy = FakeModel(legacy_result)
        self.legacy.coefficients = SimpleNamespace(lowerbound=Balance.zero("wxHOPR"))
        self.sigmoid = FakeModel(sigmoid_result)
        self.sigmoid.total_token_supply = Balance("10 wxHOPR")
        self.sigmoid.network_capacity = 2

    @property
    def models(self):
        return {LegacyParams: "legacy", SigmoidParams: "sigmoid"}


class FakePeer:
    def __init__(self, address: str, eligible: bool, delay: float | None = 2.0):
        self.address = SimpleNamespace(native=address)
        self._eligible = eligible
        self._message_delay = delay
        self.yearly_message_count = 0.0
        self.split_stake = Balance("5 wxHOPR")
        self.effective_stake = Balance("5 wxHOPR")
        self.redeemed_amount = Balance("2 wxHOPR")

    def is_eligible(self, *args, **kwargs):
        return self._eligible

    @property
    def message_delay(self):
        return self._message_delay if self.yearly_message_count is not None else None


class DummyEconomicNode(EconomicSystemMixin):
    channels: Any
    outgoing_channel_balances: dict[str, Balance]
    peers: dict[str, Any]
    peer_history: dict[str, Any]
    network_state: Any
    network_state_service: Any
    blokli_repository: Any
    sessions: dict[str, Any]
    session_destinations: list[str]
    _pending_session_creations: dict[str, Any]
    session_close_grace_period: dict[str, float]
    session_rate_limiter: Any
    _in_flight_message_tasks: set[Any]
    _in_flight_tasks_by_session_port: dict[int, set[Any]]
    ticket_price: Any
    params: Any

    def reconcile_peer_allocations(self) -> None:
        return None


@pytest.mark.asyncio
async def test_apply_economic_model_requires_complete_data(mocker):
    node = DummyEconomicNode()
    node.peers = {}
    logger_warning = mocker.patch("core.mixins.economic_system.logger.warning")

    await node.apply_economic_model()

    logger_warning.assert_called_once()


@pytest.mark.asyncio
async def test_apply_economic_model_updates_only_eligible_peers(mocker):
    node = DummyEconomicNode()
    eligible_peer = FakePeer("eligible-peer", True)
    excluded_peer = FakePeer("excluded-peer", False, delay=None)
    node.peers = cast(
        dict[str, Any],
        {
            eligible_peer.address.native: eligible_peer,
            excluded_peer.address.native: excluded_peer,
        },
    )
    node.ticket_price = cast(Any, SimpleNamespace(value=Balance("0.0001 wxHOPR")))
    node.session_destinations = ["a", "b"]
    model = FakeEconomicModel(legacy_result=90.0, sigmoid_result=30.0)
    node.params = cast(
        Any,
        SimpleNamespace(
            economic_model=model,
            sessions=SimpleNamespace(blue_destinations=["a"], green_destinations=["b"]),
            peer=SimpleNamespace(excluded_peers=[]),
        ),
    )
    gauge_set = mocker.patch("core.mixins.economic_system.ELIGIBLE_PEERS.set", new=Mock())

    await node.apply_economic_model()

    gauge_set.assert_called_once_with(1)
    assert eligible_peer.yearly_message_count == 40.0
    assert excluded_peer.yearly_message_count is None
    assert model.legacy.calls[0][2] == Balance("2 wxHOPR")
    assert model.sigmoid.calls[0][2] == [0.5, 0.5]
