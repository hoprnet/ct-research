from .blokli_provider import BlokliProvider
from .entries import (
    BlokliAccount,
    BlokliChannelGraphEntry,
    BlokliHoprBalance,
    BlokliRedemptionStats,
    BlokliTicketParameters,
)


def _field_selection(query: str, field: str) -> str:
    """Returns the `{ ... }` selection set that follows `field(...)` in a query."""
    start = query.index("{", query.index(field))
    depth = 0
    for index in range(start, len(query)):
        if query[index] == "{":
            depth += 1
        elif query[index] == "}":
            depth -= 1
            if depth == 0:
                return query[start : index + 1]
    raise ValueError(f"Unbalanced selection for {field}")


class HoprBalance(BlokliProvider[BlokliHoprBalance]):
    query_file: str = "queries/balance.graphql"
    params = ["$address: String!"]

    # Blokli caps a query's complexity at 500 by default and each `hoprBalance` costs 50, which
    # leaves room for 10; keep a margin for the selected fields.
    BATCH_SIZE = 8

    async def get_many(self, addresses: list[str]) -> dict[str, BlokliHoprBalance]:
        """
        Fetches the balances of several addresses, `BATCH_SIZE` per request, by repeating the
        `hoprBalance` query under aliases.
        """
        selection = _field_selection(self._sku_query, "hoprBalance")
        results: dict[str, BlokliHoprBalance] = {}
        for offset in range(0, len(addresses), self.BATCH_SIZE):
            chunk = addresses[offset : offset + self.BATCH_SIZE]
            variables = {f"a{i}": address for i, address in enumerate(chunk)}
            header = ", ".join(f"$a{i}: String!" for i in range(len(chunk)))
            body = " ".join(
                f"b{i}: hoprBalance(address: $a{i}) {selection}" for i in range(len(chunk))
            )
            data = await self._get_data(f"query ({header}) {{ {body} }}", variables)
            for i, address in enumerate(chunk):
                results[address] = BlokliHoprBalance({"hoprBalance": data.get(f"b{i}") or {}})
        return results


class AccountSubscription(BlokliProvider[BlokliAccount]):
    query_file: str = "queries/accounts.graphql"


class Redemptions(BlokliProvider[BlokliRedemptionStats]):
    query_file: str = "queries/redemptions.graphql"
    params = ["$filter: RedeemedStatsFilter!"]


class TicketParametersSubscription(BlokliProvider[BlokliTicketParameters]):
    query_file: str = "queries/ticket_parameters.graphql"


class ChannelGraphSubscription(BlokliProvider[BlokliChannelGraphEntry]):
    query_file: str = "queries/channel_graph.graphql"
