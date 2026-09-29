from .blokli_provider import BlokliProvider
from .entries import (
    BlokliAccount,
    BlokliChannelGraphEntry,
    BlokliHoprBalance,
    BlokliRedemptionStats,
    BlokliTicketParameters,
)


class HoprBalance(BlokliProvider[BlokliHoprBalance]):
    query_file: str = "queries/balance.graphql"
    params = ["$address: String!"]

    # Blokli caps a query's complexity at 500 by default and each `hoprBalance` costs 50, which
    # leaves room for 10; keep a margin for the selected fields.
    BATCH_SIZE = 8

    async def get_many(self, addresses: list[str]) -> dict[str, BlokliHoprBalance]:
        """Fetches the balances of several addresses, `BATCH_SIZE` per request."""
        results: dict[str, BlokliHoprBalance] = {}
        for offset in range(0, len(addresses), self.BATCH_SIZE):
            chunk = addresses[offset : offset + self.BATCH_SIZE]
            raw = await self._get_aliased("hoprBalance", "address", "String!", chunk)
            for address, entry in zip(chunk, raw):
                results[address] = BlokliHoprBalance({"hoprBalance": entry})
        return results


class AccountSubscription(BlokliProvider[BlokliAccount]):
    query_file: str = "queries/accounts.graphql"


class Redemptions(BlokliProvider[BlokliRedemptionStats]):
    query_file: str = "queries/redemptions.graphql"
    params = ["$filter: RedeemedStatsFilter!"]

    # Each `ticketRedemptionStats` costs 100 of Blokli's default 500 complexity limit.
    BATCH_SIZE = 4

    async def get_many(self, filters: list[dict]) -> list[BlokliRedemptionStats]:
        """Fetches the redemption stats of several filters, `BATCH_SIZE` per request."""
        results: list[BlokliRedemptionStats] = []
        for offset in range(0, len(filters), self.BATCH_SIZE):
            chunk = filters[offset : offset + self.BATCH_SIZE]
            raw = await self._get_aliased(
                "ticketRedemptionStats", "filter", "RedeemedStatsFilter!", chunk
            )
            results.extend(BlokliRedemptionStats({"ticketRedemptionStats": e}) for e in raw)
        return results


class TicketParametersSubscription(BlokliProvider[BlokliTicketParameters]):
    query_file: str = "queries/ticket_parameters.graphql"


class ChannelGraphSubscription(BlokliProvider[BlokliChannelGraphEntry]):
    query_file: str = "queries/channel_graph.graphql"
