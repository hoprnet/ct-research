from collections.abc import AsyncIterator, Callable

from core.blokli.entries import BlokliRedemptionStats, BlokliTicketParameters
from core.types.network_models import ChannelGraphUpdate, NodeSafeLink, SafeBalanceSnapshot


async def _empty_stream() -> AsyncIterator:
    return
    yield


class FakeNetworkRepository:
    """
    In-memory stand-in for `NetworkRepository` with harmless defaults: streams end immediately
    and lookups return nothing. Tests subclass it and override only what they exercise, so a new
    repository method only needs a default here.
    """

    def stream_node_safe_links(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[NodeSafeLink]:
        return _empty_stream()

    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]:
        return _empty_stream()

    def stream_channel_graph(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[ChannelGraphUpdate]:
        return _empty_stream()

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]:
        return []

    async def get_redeemed_amounts(
        self, pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], BlokliRedemptionStats]:
        return {}

    async def close(self) -> None:
        return None
