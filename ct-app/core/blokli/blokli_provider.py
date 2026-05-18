import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, AsyncIterator, Generic, Optional, Self, TypeVar, cast, get_args, get_origin
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from api_lib.objects import JsonResponse
from multidict import CIMultiDictProxy
from prometheus_client import Gauge

BLOKLI_CALLS = Gauge("ct_blokli_calls", "# of blokli calls")

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


TBlokliResponse = TypeVar(
    "TBlokliResponse",
    bound=JsonResponse | list[Any],
    covariant=True,
    default=JsonResponse,  # ty: ignore[invalid-legacy-type-variable]
)


class BlokliProvider(Generic[TBlokliResponse]):
    query_file: str
    params: list[str] = []
    _return_type: type[JsonResponse] | type[list[Any]] = JsonResponse
    _return_list_item_type: Optional[type[JsonResponse]] = None
    _session: Optional[aiohttp.ClientSession] = None

    def __init__(self, url: str, token: Optional[str] = None):
        self.url = self._normalize_graphql_url(url)
        self.token = token
        self.pwd = Path(str(sys.modules[self.__class__.__module__].__file__)).parent
        self._initialize_query(self.query_file, self.params)
        self._timeout = aiohttp.ClientTimeout(total=30)

    def _normalize_graphql_url(self, url: str) -> str:
        parsed = urlsplit(url)
        path = parsed.path.rstrip("/")
        if path:
            return url
        return urlunsplit((parsed.scheme, parsed.netloc, "/graphql", parsed.query, parsed.fragment))

    async def __aexit__(self, exc_type, exc, tb):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def __aenter__(self) -> Self:
        self._session = aiohttp.ClientSession()
        return self

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is BlokliProvider:
                args = get_args(base)
                if args:
                    return_type = args[0]
                    origin = get_origin(return_type)
                    if origin is list:
                        element_type = get_args(return_type)[0]
                        if isinstance(element_type, type) and issubclass(
                            element_type, JsonResponse
                        ):
                            cls._return_type = list
                            cls._return_list_item_type = element_type
                        else:
                            raise TypeError(
                                "BlokliProvider list return type must contain "
                                "JsonResponse subclasses"
                            )
                    elif isinstance(return_type, type) and issubclass(return_type, JsonResponse):
                        cls._return_type = return_type
                        cls._return_list_item_type = None
                    else:
                        raise TypeError(
                            "BlokliProvider return type must be a JsonResponse "
                            "subclass or list[JsonResponse]"
                        )
                break

    def _extract_list_payload(self, response: dict) -> list[dict]:
        payload = self._find_first_list(response)
        if payload is None:
            raise ProviderError("Expected a list in blokli response payload")

        result: list[dict] = []
        for entry in payload:
            if not isinstance(entry, dict):
                raise ProviderError("Expected list entries to be dictionaries")
            result.append(entry)
        return result

    def _find_first_list(self, payload: object) -> Optional[list[Any]]:
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for value in payload.values():
                result = self._find_first_list(value)
                if result is not None:
                    return result

        return None

    #### PRIVATE METHODS ####
    def _initialize_query(self, query_file: str, extra_inputs: Optional[list[str]] = None):
        if extra_inputs is None:
            extra_inputs = []

        self._sku_query = self._load_query(query_file, extra_inputs, operation="query")
        self._sku_subscription = self._load_query(
            query_file, extra_inputs, operation="subscription"
        )

    def _request_headers(self, sse: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        token = (self.token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if sse:
            headers["Accept"] = "text/event-stream"
        return headers

    async def _ensure_subscription_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session

        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None))
        return self._session

    def _load_query(
        self,
        path: str | Path,
        extra_inputs: Optional[list[str]] = None,
        operation: str = "query",
    ) -> str:
        """
        Loads a graphql query from a file.
        :param path: Path to the file. The path must be relative to the ct-app folder.
        :return: The query as a string.
        """
        if extra_inputs is None:
            extra_inputs = []

        inputs = [*extra_inputs]

        with open(self.pwd.joinpath(path)) as f:
            body = f.read().strip()

        lowered = body.lower()
        if lowered.startswith("query ") or lowered.startswith("query{"):
            return body
        if lowered.startswith("mutation ") or lowered.startswith("mutation{"):
            return body
        if lowered.startswith("subscription ") or lowered.startswith("subscription{"):
            return body
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*\{", body):
            return f"{operation} {body}"

        if len(inputs) > 0:
            header = operation + " (" + ",".join(inputs) + ") {"
        else:
            header = operation + " {"

        footer = "}"

        return "\n".join([header, body, footer])

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
                {
                    "url": self.url,
                    "query_preview": query[:120],
                    "variables": variable_values,
                },
            )
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=self._timeout)

            async with self._session.post(
                self.url,
                json={"query": query, "variables": variable_values},
                headers=self._request_headers(),
            ) as response:
                BLOKLI_CALLS.inc()
                logger.debug(
                    "Blokli response received",
                    {
                        "status": response.status,
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

    def _convert_response(self, response: dict) -> TBlokliResponse:
        if self._return_list_item_type is not None:
            if not response:
                return cast(TBlokliResponse, [])
            return cast(
                TBlokliResponse,
                [
                    self._return_list_item_type(entry)
                    for entry in self._extract_list_payload(response)
                ],
            )

        return cast(TBlokliResponse, self._return_type(response))

    def _parse_sse_event_data(self, event_lines: list[str]) -> Optional[dict]:
        data_lines = []
        for line in event_lines:
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

        if not data_lines:
            return None

        payload = "\n".join(data_lines)
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Failed to decode SSE JSON payload", {"payload": payload})
            return None

        if not isinstance(decoded, dict):
            logger.error("Unexpected SSE payload type", {"payload_type": type(decoded).__name__})
            return None

        if "errors" in decoded:
            logger.error("SSE stream payload contained errors", {"errors": decoded["errors"]})

        data = decoded.get("data", decoded)
        if data is None:
            return None
        if not isinstance(data, dict):
            logger.error("Unexpected SSE data type", {"payload_type": type(data).__name__})
            return None

        return data

    #### DEFAULT PUBLIC METHODS ####
    async def get(self, **kwargs) -> TBlokliResponse:
        """
        Gets the data from a blokli query.
        :param kwargs: The variables to use in the query (dict).
        :return: The data from the query.
        """

        response: dict = await self._get(**kwargs)

        if response is None:
            response = {}

        try:
            return self._convert_response(response)
        except Exception:
            logger.exception(
                "Error while converting response to return type",
                {"response": response, "return_type": self._return_type},
            )
            raise ProviderError("Error while converting response to return type")

    async def subscribe(self, **kwargs) -> AsyncIterator[TBlokliResponse]:
        logger.debug(
            "Opening blokli SSE subscription",
            {"url": self.url, "query": self._sku_subscription, "variables": kwargs},
        )
        reconnect_delay_seconds = 1.0
        max_reconnect_delay_seconds = 30.0

        while True:
            try:
                session = await self._ensure_subscription_session()
                async with session.post(
                    self.url,
                    json={"query": self._sku_subscription, "variables": kwargs},
                    headers=self._request_headers(sse=True),
                ) as response:
                    if response.status >= 400:
                        logger.error(
                            "Blokli subscription request failed",
                            {"status": response.status, "url": self.url},
                        )
                        raise ProviderError(f"Subscription failed with status {response.status}")

                    reconnect_delay_seconds = 1.0
                    event_lines: list[str] = []
                    while not response.content.at_eof():
                        raw_line = await response.content.readline()
                        if raw_line == b"":
                            break

                        line = raw_line.decode("utf-8").rstrip("\r\n")

                        if line == "":
                            if not event_lines:
                                continue

                            parsed = self._parse_sse_event_data(event_lines)
                            event_lines = []
                            if parsed is None:
                                continue
                            try:
                                yield self._convert_response(parsed)
                            except Exception:
                                logger.exception(
                                    "Error while converting subscription payload",
                                    {"response": parsed, "return_type": self._return_type},
                                )
                                raise ProviderError("Error while converting subscription payload")
                            continue

                        if line.startswith(":"):
                            continue

                        event_lines.append(line)

                    logger.warning(
                        "Blokli subscription stream closed, reconnecting",
                        {"url": self.url, "retry_in_seconds": reconnect_delay_seconds},
                    )
            except asyncio.CancelledError:
                raise
            except (asyncio.TimeoutError, aiohttp.ClientError, ProviderError) as error:
                logger.warning(
                    "Blokli subscription interrupted, reconnecting",
                    {
                        "url": self.url,
                        "error": str(error),
                        "retry_in_seconds": reconnect_delay_seconds,
                    },
                )

            await asyncio.sleep(reconnect_delay_seconds)
            reconnect_delay_seconds = min(
                reconnect_delay_seconds * 2,
                max_reconnect_delay_seconds,
            )
