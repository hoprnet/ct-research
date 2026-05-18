import asyncio
from unittest.mock import Mock
from collections.abc import AsyncIterator

import pytest

from core.blokli.entries import BlokliTicketParameters
from core.blokli.blokli_provider import ProviderError
from core.services.network_sync_orchestrator import NetworkSyncOrchestrator
from core.types.network_models import NodeSafeLink, SafeBalanceSnapshot


class RetryThenEmitRepository:
    def __init__(self):
        self.calls = 0

    def stream_node_safe_links(self) -> AsyncIterator[NodeSafeLink]:
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
