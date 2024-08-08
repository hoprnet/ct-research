import asyncio
from pathlib import Path
from typing import Union

from core.components.baseclass import Base
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from graphql.language.ast import DocumentNode


class ProviderError(Exception):
    pass


class GraphQLProvider(Base):
    def __init__(self, url: str):
        transport = AIOHTTPTransport(url=url)
        self.pwd = Path(__file__).parent.joinpath("queries")
        self._client = Client(transport=transport)
        self._default_key = None

    #### PRIVATE METHODS ####
    def _load_query(self, path: Union[str, Path]) -> tuple[str, DocumentNode]:
        """
        Loads a graphql query from a file.
        :param path: Path to the file. The path must be relative to the ct-app folder.
        :return: The query as a gql object.
        """

        header = "query ($first: Int!, $skip: Int!) {"
        footer = "}"
        with open(self.pwd.joinpath(path)) as f:
            body = f.read()

        return body.split("(")[0], gql("\n".join([header, body, footer]))

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
            raise ProviderError(f"TransportQueryError error: {err}")
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

        # call `self._execute(self._sku_query, vars)` with a timeout
        try:
            response = await asyncio.wait_for(
                self._execute(self._sku_query, vars), timeout=30
            )
        except asyncio.TimeoutError:
            self.error("Query timeout occurred")
            return False

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

            try:
                response = await asyncio.wait_for(
                    self._execute(self._sku_query, vars), timeout=30
                )
            except asyncio.TimeoutError:
                self.error("Timeout error while fetching data from subgraph.")
                break
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

        try:
            result = await self._test_query(self._default_key, **kwargs)
        except ProviderError as err:
            self.error(f"ProviderError error: {err}")
            result = None

        if result is None:
            return False

        return result


class SafesProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("safes_balance.graphql")


class StakingProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("staking.graphql")


class RewardsProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("rewards.graphql")


class AllocationsProvider(GraphQLProvider):
    def __init__(self, url: str):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("allocations.graphql")
