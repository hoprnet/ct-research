import asyncio
import logging
from collections.abc import Callable
from typing import AsyncIterator, Protocol

from ..blokli.adapters import (
    to_channel,
    to_node_safe_link_from_account,
    to_safe_balance_snapshot,
)
from ..blokli.entries import BlokliRedemptionStats, BlokliTicketParameters
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

    async def get_redeemed_amounts(
        self, pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], BlokliRedemptionStats]: ...

    async def close(self) -> None: ...


class GraphqlNetworkRepository:
    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token
        # Query providers are kept for the repository's lifetime so their HTTP session is reused
        # across refreshes; subscriptions hold their own long-lived connection.
        self._balances: HoprBalance | None = None
        self._redemptions: Redemptions | None = None

    def _balances_client(self) -> HoprBalance:
        if self._balances is None:
            self._balances = HoprBalance(self.url, self.token)
        return self._balances

    def _redemptions_client(self) -> Redemptions:
        if self._redemptions is None:
            self._redemptions = Redemptions(self.url, self.token)
        return self._redemptions

    async def close(self) -> None:
        for client in (self._balances, self._redemptions):
            if client is not None:
                await client.__aexit__(None, None, None)
        self._balances = None
        self._redemptions = None

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
        client = self._balances_client()
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

    async def get_redeemed_amounts(
        self, pairs: list[tuple[str, str]]
    ) -> dict[tuple[str, str], BlokliRedemptionStats]:
        """
        Fetches the redemption stats of several (safe, node) pairs, a few per request. A pair
        whose batch failed is missing from the result.
        """
        client = self._redemptions_client()
        semaphore = asyncio.Semaphore(4)
        size = Redemptions.BATCH_SIZE
        chunks = [pairs[i : i + size] for i in range(0, len(pairs), size)]

        async def fetch_chunk(chunk: list[tuple[str, str]]):
            filters = [{"safeAddress": safe, "nodeAddress": node} for safe, node in chunk]
            async with semaphore:
                return chunk, await client.get_many(filters)

        results: dict[tuple[str, str], BlokliRedemptionStats] = {}
        for outcome in await asyncio.gather(
            *(fetch_chunk(chunk) for chunk in chunks), return_exceptions=True
        ):
            if isinstance(outcome, BaseException):
                logger.warning("Failed to fetch redeemed amounts", {"error": str(outcome)})
                continue
            chunk, stats = outcome
            results.update(zip(chunk, stats))
        return results
