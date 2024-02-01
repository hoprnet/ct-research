from pathlib import Path

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError


class ProviderError(Exception):
    pass


class GraphQLProvider:
    def __init__(self, url: str):
        transport = AIOHTTPTransport(url=url)
        self.pwd = Path(__file__).parent.parent.parent
        self._client = Client(transport=transport)

    def _load_query(self, path: str or Path):
        with open(self.pwd.joinpath(path)) as f:
            return gql(f.read())

    async def _execute(self, query, variable_values):
        try:
            return await self._client.execute_async(
                query, variable_values=variable_values
            )
        except TransportQueryError as err:
            raise ProviderError(err.errors[0]["message"])


class SafesProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._sku_query = self._load_query(
            "core/subgraph_queries/safes_balance.graphql"
        )

    async def get_safes(self, page_size: int = 1000):
        skip = 0
        safes = []

        while True:
            vars = {"first": page_size, "skip": skip}
            response = await self._execute(self._sku_query, vars)

            if "safes" not in response:
                break

            safes.extend(response["safes"])

            skip += page_size
            if len(response["safes"]) < page_size:
                break

        return safes

    async def test_connection(self) -> bool:
        vars = {"first": 1, "skip": 0}
        response = await self._execute(self._sku_query, vars)

        return response and "safes" in response


class StakingProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._sku_query = self._load_query("core/subgraph_queries/staking.graphql")

    async def get_nfts(self, page_size: int = 1000) -> list[dict[dict]]:
        skip = 0

        nfts = []
        while True:
            vars = {"first": page_size, "skip": skip}
            response = await self._execute(self._sku_query, vars)

            if "boosts" not in response:
                break

            nfts.extend(response["boosts"])
            skip += page_size

            if len(response["boosts"]) < page_size:
                break

        return nfts


class wxHOPRTransactionProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._sku_query = self._load_query(
            "core/subgraph_queries/wxhopr_transactions.graphql"
        )

    async def get_transactions(self, to: str, page_size: int = 1000):
        skip = 0
        transactions = []
        while True:
            vars = {"first": page_size, "skip": skip, "to": to}
            response = await self._execute(self._sku_query, vars)

            if "transactions" not in response:
                break

            transactions.extend(response["transactions"])

            skip += page_size
            if len(response["transactions"]) < page_size:
                break

        return transactions
