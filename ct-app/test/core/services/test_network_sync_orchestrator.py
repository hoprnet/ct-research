import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
from collections.abc import AsyncIterator

import pytest

from core.blokli.entries import BlokliRedemptionStats, BlokliTicketParameters
from core.blokli.blokli_provider import ProviderError
from core.services.link_state_store import LinkStateStore
from core.services.network_sync_orchestrator import NetworkSyncOrchestrator
from core.types.balance import Balance
from core.types.network_models import ChannelGraphUpdate, NodeSafeLink, SafeBalanceSnapshot
from core.types.network_state import NetworkState
from core.types.network_updates import LinkUpdate


class RetryThenEmitRepository:
    def __init__(self):
        self.calls = 0

    def stream_node_safe_links(self, on_connect=None) -> AsyncIterator[NodeSafeLink]:
        async def _stream():
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("subscription failed")
            if self.calls == 2:
                yield NodeSafeLink(node_address="0xnode", safe_address="0xsafe")
                raise asyncio.CancelledError

        return _stream()

    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]:
        raise NotImplementedError

    def stream_channel_graph(self, on_connect=None) -> AsyncIterator[ChannelGraphUpdate]:
        raise NotImplementedError

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]:
        raise NotImplementedError

    async def get_redeemed_amount(self, safe_address: str, node_address: str):
        raise NotImplementedError


@pytest.mark.asyncio
async def test_stream_link_updates_retries_after_provider_error():
    repository = RetryThenEmitRepository()
    state_service = Mock()
    state_service.make_link_update.return_value = "update"
    on_update = Mock()

    orchestrator = NetworkSyncOrchestrator(repository, state_service)

    with pytest.raises(asyncio.CancelledError):
        await orchestrator.stream_link_updates(on_update)

    assert repository.calls == 2
    state_service.make_link_update.assert_called_once_with("0xnode", "0xsafe")
    state_service.apply_link_updates.assert_called_once_with(["update"])
    on_update.assert_called_once_with()


class RedemptionRepository(RetryThenEmitRepository):
    def __init__(self, result):
        super().__init__()
        self.result = result

    async def get_redeemed_amount(self, safe_address: str, node_address: str):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _peer(address: str):
    return SimpleNamespace(
        safe_address="0xsafe",
        node_address=address,
        address=SimpleNamespace(native=address),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [
        BlokliRedemptionStats({}),
        BlokliRedemptionStats(
            {
                "ticketRedemptionStats": {
                    "__typename": "QueryFailedError",
                    "code": "QUERY_FAILED",
                    "message": "boom",
                }
            }
        ),
        None,
        ProviderError("request failed"),
    ],
)
async def test_refresh_redeemed_keeps_previous_value_on_error(result):
    state_service = Mock()
    orchestrator = NetworkSyncOrchestrator(RedemptionRepository(result), state_service)

    await orchestrator.refresh_redeemed({"0xnode": _peer("0xnode")})

    state_service.make_redeemed_update.assert_not_called()
    state_service.apply_redeemed_updates.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_redeemed_applies_valid_result():
    result = BlokliRedemptionStats(
        {"ticketRedemptionStats": {"__typename": "RedeemedStats", "redeemedAmount": "3 wxHOPR"}}
    )
    state_service = Mock()
    state_service.make_redeemed_update.return_value = "update"
    orchestrator = NetworkSyncOrchestrator(RedemptionRepository(result), state_service)
    peers = {"0xnode": _peer("0xnode")}

    await orchestrator.refresh_redeemed(peers)

    state_service.make_redeemed_update.assert_called_once_with(
        "0xnode", "0xsafe", "0xnode", Balance("3 wxHOPR")
    )
    state_service.apply_redeemed_updates.assert_called_once_with(["update"], peers)


def test_link_state_store_removes_unlinked_node():
    state = NetworkState()
    store = LinkStateStore(state)

    store.apply_link_updates([LinkUpdate(node_address="0xnode", safe_address="0xsafe")])
    assert state.node_to_safe == {"0xnode": "0xsafe"}

    store.apply_link_updates([LinkUpdate(node_address="0xnode", safe_address=None)])
    assert state.node_to_safe == {}


def test_link_state_store_sweeps_links_missing_from_new_snapshot():
    state = NetworkState()
    store = LinkStateStore(state)
    store.start_generation()
    store.apply_link_updates(
        [
            LinkUpdate(node_address="0xkept", safe_address="0xsafe"),
            LinkUpdate(node_address="0xgone", safe_address="0xsafe"),
        ]
    )

    # Reconnect: the new snapshot no longer lists 0xgone.
    store.start_generation()
    store.apply_link_updates([LinkUpdate(node_address="0xkept", safe_address="0xsafe")])

    assert set(state.node_to_safe) == {"0xkept", "0xgone"}  # kept until the sweep
    assert store.sweep() == 1
    assert state.node_to_safe == {"0xkept": "0xsafe"}


class ConnectThenEmitRepository(RetryThenEmitRepository):
    def stream_node_safe_links(self, on_connect=None) -> AsyncIterator[NodeSafeLink]:
        async def _stream():
            on_connect()
            yield NodeSafeLink(node_address="0xnode", safe_address="0xsafe")
            raise asyncio.CancelledError

        return _stream()


@pytest.mark.asyncio
async def test_stream_link_updates_sweeps_after_each_connection(mocker):
    state = NetworkState()
    store = LinkStateStore(state)
    state_service = Mock()
    state_service.make_link_update.side_effect = lambda node, safe: LinkUpdate(node, safe)
    state_service.apply_link_updates.side_effect = store.apply_link_updates
    state_service.start_link_generation.side_effect = store.start_generation
    state_service.sweep_links.side_effect = store.sweep
    mocker.patch("core.services.network_sync_orchestrator.SNAPSHOT_SWEEP_DELAY_SECONDS", 0)

    orchestrator = NetworkSyncOrchestrator(ConnectThenEmitRepository(), state_service)
    on_update = Mock()
    with pytest.raises(asyncio.CancelledError):
        await orchestrator.stream_link_updates(on_update)

    state_service.start_link_generation.assert_called_once_with()
    await orchestrator._link_sweep_task  # let the scheduled sweep run
    state_service.sweep_links.assert_called_once_with()
    assert state.node_to_safe == {"0xnode": "0xsafe"}
    await orchestrator.close()


@pytest.mark.asyncio
async def test_get_safe_balances_batches_lookups(mocker):
    from core.blokli.providers import HoprBalance
    from core.services.blokli_repository import GraphqlNetworkRepository

    sent: list[dict] = []

    async def fake_get_data(self, query, variables):
        sent.append(variables)
        return {
            f"b{i}": (
                {"__typename": "HoprBalance", "address": address, "balance": "5 wxHOPR"}
                if address != "0xsafe3"
                else {"__typename": "QueryFailedError", "code": "X", "message": "boom"}
            )
            for i, address in enumerate(variables.values())
        }

    mocker.patch.object(HoprBalance, "_get_data", fake_get_data)
    safes = [f"0xsafe{i}" for i in range(10)]

    balances = await GraphqlNetworkRepository("http://blokli/graphql").get_safe_balances(safes)

    assert sorted(len(batch) for batch in sent) == [2, 8]
    assert sorted(b.safe_address for b in balances) == sorted(s for s in safes if s != "0xsafe3")
