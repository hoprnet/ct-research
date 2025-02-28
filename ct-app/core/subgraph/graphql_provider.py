import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Union

import aiohttp
from prometheus_client import Gauge

from core.components.logs import configure_logging

from .mode import Mode
from .url import URL

SUBGRAPH_CALLS = Gauge("ct_subgraph_calls",
                       "# of subgraph calls", ["slug", "type"])
SUBGRAPH_IN_USE = Gauge("ct_subgraph_in_use", "Subgraph in use", ["slug"])

configure_logging()
logger = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


class GraphQLProvider:
    query_file: str = None
    params: list[str] = []
    default_key: list[str] = None

    def __init__(self, url: URL):
        self.url = url
        self.pwd = Path(sys.modules[self.__class__.__module__].__file__).parent
        self._initialize_query(self.query_file, self.params)

    #### PRIVATE METHODS ####
    def _initialize_query(
        self, query_file: str, extra_inputs: Optional[list[str]] = None
    ):
        if extra_inputs is None:
            extra_inputs = []

        keys, self._sku_query = self._load_query(query_file, extra_inputs)

        if self.default_key is None:
            self.default_key = keys

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
                self.url.url, json={"query": query,
                                    "variables": variable_values}
            ) as response:
                SUBGRAPH_CALLS.labels(
                    self.url.params.slug, self.url.mode).inc()
                return await response.json(), response.headers
        except TimeoutError as err:
            logger.error("Timeout error", {"error": str(err)})
        except Exception as err:
            logger.error("Unknown error", {"error": str(err)})
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
            logger.debug("Testing subgraph endpoint", {
                "url": self.url.url, "mode": self.url.mode.value, "key": key, **kwargs})
            response, _ = await asyncio.wait_for(
                self._execute(self._sku_query, kwargs), timeout=30
            )
        except asyncio.TimeoutError:
            logger.error("Query timeout occurred", {
                         "url": self.url.url, "mode": self.url.mode.value, "key": key, **kwargs})
            return False
        except ProviderError as err:
            logger.error("ProviderError error",
                         {"error": str(err), "url": self.url.url, "mode": self.url.mode.value, "key": key, **kwargs})
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
                logger.exception(
                    "Timeout error while fetching data from subgraph")
                break
            except ProviderError as err:
                logger.exception("ProviderError error", {"error": str(err)})
                break

            if response is None:
                break

            if "errors" in response:
                logger.error(f"Internal error: {response['errors']}")

            try:
                content = response.get("data", dict()).get(key, [])
            except Exception as err:
                logger.error("Error while fetching data from subgraph", {
                             "error": str(err), "data": response})
                break
            data.extend(content)

            skip += page_size
            if len(content) < page_size:
                break

        try:
            if headers is not None:
                attestations = json.loads(
                    headers.getall("graph-attestation")[0])
                logger.debug(
                    "Subgraph attestations", {"attestations": attestations}
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

        if key is None and self.default_key is not None:
            key = self.default_key
        else:
            logger.warning(
                "No key provided for the query, and no default key set. Skipping query..."
            )
            return []

        if inputs := getattr(self.url.params, "inputs", None):
            kwargs.update(vars(inputs))
        return await self._get(key, **kwargs)

    async def test(self, method: str, **kwargs):
        """
        Tests a subgraph query using the default key.
        :param kwargs: The variables to use in the query (dict).
        :return: True if the query is successful, False otherwise.
        """
        if self.default_key is None:
            logger.warning(
                "No key provided for the query, and no default key set. Skipping test query..."
            )
            return False

        if method != "auto":
            self.url.mode = Mode.fromString(method)
        else:
            for mode in Mode.callables():
                self.url.mode = mode
                try:
                    result = await self._test_query(self.default_key, **kwargs)
                except ProviderError as err:
                    logger.error(f"ProviderError error: {err}")

                if result is True:
                    break
            else:
                self.url.mode = Mode.NONE

        if self.url.mode == Mode.NONE:
            logger.warning(
                f"No subgraph available for '{self.url.params.slug}'")

        logger.debug("Subgraph endpoint probing done", {
            "url": self.url.url, "mode": self.url.mode.value, "result": result, **kwargs})
        SUBGRAPH_IN_USE.labels(self.url.params.slug).set(
            self.url.mode.to_int())
        return self.url.mode
