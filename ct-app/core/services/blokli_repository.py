import asyncio
import logging
from collections.abc import Callable
from typing import AsyncIterator, Protocol

from ..blokli.adapters import (
    to_channel,
    to_node_safe_link_from_account,
    to_safe_balance_snapshot,
)
from ..blokli.entries import BlokliTicketParameters
from ..blokli.providers import (
    AccountSubscription,
    ChannelGraphSubscription,
    HoprBalance,
    Redemptions,
    TicketParametersSubscription,
)
from ..types.network_models import ChannelGraphUpdate, NodeSafeLink, SafeBalanceSnapshot

logger = logging.getLogger(__name__)


class NetworkRepository(Protocol):
    def stream_node_safe_links(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[NodeSafeLink]: ...
    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]: ...
    def stream_channel_graph(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[ChannelGraphUpdate]: ...

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]: ...

    async def get_redeemed_amount(self, safe_address: str, node_address: str): ...


class GraphqlNetworkRepository:
    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token

    def stream_node_safe_links(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[NodeSafeLink]:
        async def _stream() -> AsyncIterator[NodeSafeLink]:
            async with AccountSubscription(self.url, self.token) as client:
                async for account in client.subscribe(on_connect=on_connect):
                    logger.debug(
                        "Account subscription event",
                        {
                            "node_address": account.node_address,
                            "safe_address": account.safe_address,
                        },
                    )
                    link = to_node_safe_link_from_account(account)
                    if link is None:
                        logger.debug("Dropping account update without node address")
                        continue
                    yield link

        return _stream()

    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]:
        async def _stream() -> AsyncIterator[BlokliTicketParameters]:
            async with TicketParametersSubscription(self.url, self.token) as client:
                async for params in client.subscribe():
                    logger.debug(
                        "Ticket parameters subscription event",
                        {
                            "ticket_price": params.ticket_price.as_str,
                            "min_ticket_winning_probability": params.min_ticket_winning_probability,
                        },
                    )
                    yield params

        return _stream()

    def stream_channel_graph(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[ChannelGraphUpdate]:
        """
        Streams the network's non-closed channels: a full snapshot on every (re)connection,
        then each change. A channel reported as closed must be dropped.
        """

        async def _stream() -> AsyncIterator[ChannelGraphUpdate]:
            async with ChannelGraphSubscription(self.url, self.token) as client:
                async for entry in client.subscribe(on_connect=on_connect):
                    channel = to_channel(entry)
                    if channel is None:
                        logger.debug("Dropping incomplete channel graph entry")
                        continue
                    yield ChannelGraphUpdate(channel_id=entry.channel_id, channel=channel)

        return _stream()

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]:
        balances: list[SafeBalanceSnapshot] = []
        async with HoprBalance(self.url, self.token) as client:
            semaphore = asyncio.Semaphore(4)
            size = HoprBalance.BATCH_SIZE
            chunks = [safe_addresses[i : i + size] for i in range(0, len(safe_addresses), size)]

            async def fetch_chunk(chunk: list[str]):
                async with semaphore:
                    return await client.get_many(chunk)

            results = await asyncio.gather(
                *(fetch_chunk(chunk) for chunk in chunks),
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    logger.warning("Failed to fetch safe balances", {"error": str(result)})
                    continue
                for safe_address, response in result.items():
                    if not response.is_valid:
                        logger.warning(
                            "Blokli returned no safe balance",
                            {"safe_address": safe_address, "error": response.error},
                        )
                        continue
                    snapshot = to_safe_balance_snapshot(response)
                    if snapshot is not None:
                        balances.append(snapshot)
        logger.debug(
            "Fetched safe balances",
            {"requested": len(safe_addresses), "received": len(balances)},
        )
        return balances

    async def get_redeemed_amount(self, safe_address: str, node_address: str):
        async with Redemptions(self.url, self.token) as client:
            return await client.get(
                filter={"safeAddress": safe_address, "nodeAddress": node_address}
            )
