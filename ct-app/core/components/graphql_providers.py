from pathlib import Path

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from graphql.language.ast import DocumentNode

from .baseclass import Base

class GraphQLProvider(Base):
    def __init__(self, url: str):
        transport = AIOHTTPTransport(url=url)
        self.pwd = Path(__file__).parent.parent.parent
        self._client = Client(transport=transport)
        self._default_key = None

    #### PRIVATE METHODS ####
    def _load_query(self, path: str or Path) -> DocumentNode:
        """
        Loads a graphql query from a file.
        :param path: Path to the file. The path must be relative to the ct-app folder.
        :return: The query as a gql object.
        """
        with open(self.pwd.joinpath(path)) as f:
            return gql(f.read())

    async def _execute(self, query: DocumentNode, variable_values: dict):
        """
        Executes a graphql query.
        :param query: The query to execute.
        :param variable_values: The variables to use in the query (dict)"""
        try:
            return await self._client.execute_async(
                query, variable_values=variable_values
            )
        except TransportQueryError as err:
            self.error(f"TransportQueryError error: {err}")
        except TimeoutError as err:
            self.error(f"Timeout error: {err}")
        except Exception as err:
            self.error(f"Unknown error: {err}")

    async def _test_query(self, key: str, **kwargs) -> bool:
        """
        Tests a subgraph query.
        :param key: The key to look for in the response.
        :param kwargs: The variables to use in the query (dict).
        :return: True if the query is successful, False otherwise.
        """
        vars = {"first": 1, "skip": 0}
        vars.update(kwargs)
        response = await self._execute(self._sku_query, vars)

        return response and key in response

    async def _get(self, key: str, **kwargs) -> dict:
        """
        Gets the data from a subgraph query.
        :param key: The key to look for in the response.
        :param kwargs: The variables to use in the query (dict).
        :return: The data from the query.
        """
        page_size = 1000
        skip = 0
        data = []

        while True:
            vars = {"first": page_size, "skip": skip}
            vars.update(kwargs)

            response = await self._execute(self._sku_query, vars)
            
            if response is None:
                break

            content = response.get(key, [])
            data.extend(content)

            skip += page_size
            if len(content) < page_size:
                break

        return data

    #### DEFAULT PUBLIC METHODS ####
    async def get(self, key: str = None, **kwargs):
        """
        Gets the data from a subgraph query.
        :param key: The key to look for in the response. If None, the default key is used.
        :param kwargs: The variables to use in the query (dict).
        :return: The data from the query.
        """

        if key is None and self._default_key is not None:
            key = self._default_key
        else:
            self.warning(
                "No key provided for the query, and no default key set. Skipping query..."
            )
            return []

        return await self._get(key, **kwargs)

    async def test(self, **kwargs):
        """
        Tests a subgraph query using the default key.
        :param kwargs: The variables to use in the query (dict).
        :return: True if the query is successful, False otherwise.
        """
        if self._default_key is None:
            self.warning(
                "No key provided for the query, and no default key set. Skipping test query..."
            )
            return False

        result = await self._test_query(self._default_key, **kwargs)

        if result is None:
            return False
        
        return result

class SafesProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key = "safes"
        self._sku_query = self._load_query(
            "core/subgraph_queries/safes_balance.graphql"
        )

    @property
    def print_prefix(self) -> str:
        return "safe-provider"


class StakingProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key = "boosts"
        self._sku_query = self._load_query("core/subgraph_queries/staking.graphql")

    @property
    def print_prefix(self) -> str:
        return "staking-provider"


class wxHOPRTransactionProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key = "transactions"
        self._sku_query = self._load_query(
            "core/subgraph_queries/wxhopr_transactions.graphql"
        )

    @property
    def print_prefix(self) -> str:
        return "transaction-provider"
