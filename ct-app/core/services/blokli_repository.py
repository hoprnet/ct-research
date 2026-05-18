import asyncio
import logging
from typing import AsyncIterator, Protocol

from ..blokli.adapters import (
    to_node_safe_link_from_account,
    to_safe_balance_snapshot,
)
from ..blokli.entries import BlokliTicketParameters
from ..blokli.providers import (
    AccountSubscription,
    HoprBalance,
    Redemptions,
    TicketParametersSubscription,
)
from ..types.network_models import NodeSafeLink, SafeBalanceSnapshot

logger = logging.getLogger(__name__)


class NetworkRepository(Protocol):
    def stream_node_safe_links(self) -> AsyncIterator[NodeSafeLink]: ...
    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]: ...

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]: ...

    async def get_redeemed_amount(self, safe_address: str, node_address: str): ...


class GraphqlNetworkRepository:
    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token

    def stream_node_safe_links(self) -> AsyncIterator[NodeSafeLink]:
        async def _stream() -> AsyncIterator[NodeSafeLink]:
            async with AccountSubscription(self.url, self.token) as client:
                async for account in client.subscribe():
                    logger.debug(
                        "Account subscription event",
                        {
                            "node_address": account.node_address,
                            "safe_address": account.safe_address,
                        },
                    )
                    link = to_node_safe_link_from_account(account)
                    if link is None:
                        logger.debug("Dropping account update without safe link")
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

    async def get_safe_balances(self, safe_addresses: list[str]) -> list[SafeBalanceSnapshot]:
        balances: list[SafeBalanceSnapshot] = []
        async with HoprBalance(self.url, self.token) as client:
            semaphore = asyncio.Semaphore(10)

            async def fetch_one(safe_address: str) -> SafeBalanceSnapshot | None:
                async with semaphore:
                    response = await client.get(address=safe_address)
                snapshot = to_safe_balance_snapshot(response)
                return snapshot

            snapshots = await asyncio.gather(
                *(fetch_one(safe_address) for safe_address in safe_addresses)
            )
            for snapshot in snapshots:
                if snapshot is None:
                    continue
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
