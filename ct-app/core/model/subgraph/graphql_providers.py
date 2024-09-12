import asyncio
from pathlib import Path
from typing import Union

import aiohttp
from core.components.baseclass import Base
from prometheus_client import Gauge

from .subgraph_type import SubgraphType
from .subgraph_url import SubgraphURL

SUBGRAPH_CALLS = Gauge("ct_subgraph_calls", "# of subgraph calls", ["slug", "type"])
SUBGRAPH_IN_USE = Gauge("ct_subgraph_in_use", "Subgraph in use", ["slug"])


class ProviderError(Exception):
    pass


class GraphQLProvider(Base):
    def __init__(self, url: SubgraphURL):
        self.url = url
        self.pwd = Path(__file__).parent.joinpath("queries")
        self._default_key = None

    #### PRIVATE METHODS ####
    def _load_query(self, path: Union[str, Path], extra_inputs: list[str] = []) -> str:
        """
        Loads a graphql query from a file.
        :param path: Path to the file. The path must be relative to the ct-app folder.
        :return: The query as a string.
        """
        inputs = ["$first: Int!", "$skip: Int!", *extra_inputs]

        header = "query (" + ",".join(inputs) + ") {"
        footer = "}"
        with open(self.pwd.joinpath(path)) as f:
            body = f.read()

        return body.split("(")[0], ("\n".join([header, body, footer]))

    async def _execute(self, query: str, variable_values: dict) -> tuple[dict, dict]:
        """
        Executes a graphql query.
        :param query: The query to execute.
        :param variable_values: The variables to use in the query (dict)"""

        try:
            async with aiohttp.ClientSession() as session, session.post(
                self.url.url, json={"query": query, "variables": variable_values}
            ) as response:
                SUBGRAPH_CALLS.labels(self.url.params.slug, self.url.type).inc()
                return await response.json(), response.headers
        except TimeoutError as err:
            self.error(f"Timeout error: {err}")
        except Exception as err:
            self.error(f"Unknown error: {err}")
        return {}, None

    async def _test_query(self, key: str, **kwargs) -> bool:
        """
        Tests a subgraph query.
        :param key: The key to look for in the response.
        :param kwargs: The variables to use in the query (dict).
        :return: True if the query is successful, False otherwise.
        """
        kwargs.update({"first": 1, "skip": 0})

        try:
            response, _ = await asyncio.wait_for(
                self._execute(self._sku_query, kwargs), timeout=30
            )
        except asyncio.TimeoutError:
            self.error("Query timeout occurred")
            return False
        except ProviderError as err:
            self.error(f"ProviderError error: {err}")
            return False

        return key in response.get("data", [])

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
            kwargs.update({"first": page_size, "skip": skip})

            try:
                response, headers = await asyncio.wait_for(
                    self._execute(self._sku_query, kwargs), timeout=30
                )
            except asyncio.TimeoutError:
                self.error("Timeout error while fetching data from subgraph.")
                break
            except ProviderError as err:
                self.error(f"ProviderError error: {err}")
                break

            if response is None:
                break

            if "errors" in response:
                self.error(f"Internal error: {response['errors']}")

            try:
                content = response.get("data", dict()).get(key, [])
            except Exception as err:
                self.error(f"Error while fetching data from subgraph: {err}")
                break
            data.extend(content)

            skip += page_size
            if len(content) < page_size:
                break

        try:
            if headers is not None:
                self.debug(
                    f"Subgraph attestations {headers.getall('graph-attestation')}"
                )
        except UnboundLocalError:
            # raised if the headers variable is not defined
            pass
        except KeyError:
            # raised if using the centralized endpoint
            pass
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

    async def test(self, method: str, **kwargs):
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

        if method != "auto":
            self.url.type = SubgraphType.fromString(method)
        else:
            for type in SubgraphType.callables():
                self.url.type = type
                try:
                    result = await self._test_query(self._default_key, **kwargs)
                except ProviderError as err:
                    self.error(f"ProviderError error: {err}")

                if result is True:
                    break
            else:
                self.url.type = SubgraphType.NONE

        if self.url.type == SubgraphType.NONE:
            self.warning(f"No subgraph available for '{self.url.params.slug}'")

        # self.info(f"Using {self.url.type} for {self.url.params.slug}")

        SUBGRAPH_IN_USE.labels(self.url.params.slug).set(self.url.type.toInt())
        return self.url.type


class SafesProvider(GraphQLProvider):
    def __init__(self, url: SubgraphURL):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("safes_balance.graphql")


class StakingProvider(GraphQLProvider):
    def __init__(self, url: SubgraphURL):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("staking.graphql")


class RewardsProvider(GraphQLProvider):
    def __init__(self, url: SubgraphURL):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query("rewards.graphql")


class AllocationsProvider(GraphQLProvider):
    def __init__(self, url: SubgraphURL):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query(
            "allocations.graphql",
            extra_inputs=['$schedule_in: [String!] = [""]'],
        )


class EOABalanceProvider(GraphQLProvider):
    def __init__(self, url: SubgraphURL):
        super().__init__(url)
        self._default_key, self._sku_query = self._load_query(
            "eoa_balance.graphql",
            extra_inputs=['$id_in: [Bytes!] = [""]'],
        )
