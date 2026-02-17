import asyncio
import logging
import sys
from pathlib import Path
from typing import Generic, Optional, TypeVar, get_args, get_origin

import aiohttp
from api_lib.objects import JsonResponse
from multidict import CIMultiDictProxy
from prometheus_client import Gauge

from ..components.logs import configure_logging

BLOKLI_CALLS = Gauge("ct_blokli_calls", "# of blokli calls")

configure_logging()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ProviderError(Exception):
    pass


TBlokliResponse = TypeVar(
    "TBlokliResponse",
    bound=JsonResponse,
    covariant=True,
    default=JsonResponse,  # ty: ignore[invalid-legacy-type-variable]
)


class BlokliProvider(Generic[TBlokliResponse]):
    query_file: str
    params: list[str] = []
    _return_type: type[TBlokliResponse] = JsonResponse  # ty: ignore[invalid-assignment]
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self, url: str, token: Optional[str] = None):
        self.url = url
        self.token = token
        self.pwd = Path(str(sys.modules[self.__class__.__module__].__file__)).parent
        self._initialize_query(self.query_file, self.params)
        self._timeout = aiohttp.ClientTimeout(total=30)

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is BlokliProvider:
                args = get_args(base)
                if args:
                    cls._return_type = args[0]
                break

    #### PRIVATE METHODS ####
    def _initialize_query(self, query_file: str, extra_inputs: Optional[list[str]] = None):
        if extra_inputs is None:
            extra_inputs = []

        self._sku_query = self._load_query(query_file, extra_inputs)

    def _load_query(self, path: str | Path, extra_inputs: Optional[list[str]] = None) -> str:
        """
        Loads a graphql query from a file.
        :param path: Path to the file. The path must be relative to the ct-app folder.
        :return: The query as a string.
        """
        if extra_inputs is None:
            extra_inputs = []

        with open(self.pwd.joinpath(path)) as f:
            return f.read()

    async def _execute(
        self, query: str, variable_values: dict
    ) -> tuple[dict, Optional[CIMultiDictProxy]]:
        """
        Executes a graphql query.
        :param query: The query to execute.
        :param variable_values: The variables to use in the query (dict)"""

        try:
            logger.debug(
                "Executing blokli query",
                {"url": self.url, "query": query, "variables": variable_values},
            )
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=self._timeout)

            async with self._session.post(
                self.url, json={"query": query, "variables": variable_values}
            ) as response:
                BLOKLI_CALLS.inc()
                logger.debug(
                    "Blokli response received",
                    {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text(),
                    },
                )
                if response.status >= 400:
                    logger.error(
                        "Blokli request failed",
                        {"status": response.status, "url": self.url},
                    )

                return await response.json(), response.headers

        except TimeoutError as err:
            logger.error("Timeout error", {"error": str(err)})
        except Exception as err:
            logger.error("Unknown error", {"error": str(err)})
        return {}, None

    async def _get(self, **kwargs) -> dict:
        """
        Gets the data from a blokli query.
        :param kwargs: The variables to use in the query (dict).
        :return: The data from the query.
        """

        try:
            response, headers = await asyncio.wait_for(
                self._execute(self._sku_query, kwargs), timeout=30
            )
        except asyncio.TimeoutError:
            logger.error("Timeout error while fetching data from blokli")
            return {}
        except ProviderError:
            logger.exception("ProviderError error")
            return {}

        if response is None:
            return {}

        if "errors" in response:
            logger.error(f"Internal error: {response.get('errors')}")

        try:
            content = response.get("data", dict())
        except Exception:
            logger.exception(
                "Error while fetching data from blokli",
                {"data": response},
            )
            return {}

        return content

    #### DEFAULT PUBLIC METHODS ####
    async def get(self, **kwargs) -> TBlokliResponse:
        """
        Gets the data from a blokli query.
        :param kwargs: The variables to use in the query (dict).
        :return: The data from the query.
        """

        response: dict = await self._get(**kwargs)

        logger.info("Blokli response", {"response": response})

        if response is None:
            return self._return_type({})

        try:
            return self._return_type(response)
        except Exception:
            logger.exception(
                "Error while converting response to return type",
                {"response": response, "return_type": self._return_type},
            )
            raise ProviderError("Error while converting response to return type")
