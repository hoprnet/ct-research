import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import (
    AsyncIterator,
    Callable,
    Generic,
    Optional,
    Self,
    TypeVar,
    cast,
    get_args,
    get_origin,
)
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from api_lib.objects import JsonResponse
from prometheus_client import Counter, Gauge

BLOKLI_CALLS = Counter(
    "ct_blokli_calls",
    "Total Blokli API calls",
    ["type", "target", "result"],
)
SUBSCRIPTION_CONNECTED = Gauge(
    "ct_blokli_subscription_connected",
    "1 while the Blokli subscription stream is connected",
    ["subscription"],
)
SUBSCRIPTION_LAST_EVENT = Gauge(
    "ct_blokli_subscription_last_event_timestamp",
    "Unix time of the last event received on the Blokli subscription",
    ["subscription"],
)

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


TBlokliResponse = TypeVar(
    "TBlokliResponse",
    bound=JsonResponse,
    covariant=True,
    default=JsonResponse,
)



class BlokliProvider(Generic[TBlokliResponse]):
    query_file: str
    _return_type: type[JsonResponse] = JsonResponse
    _subscription_session: Optional[aiohttp.ClientSession] = None

    def __init__(self, url: str, token: Optional[str] = None):
        self.url = self._normalize_graphql_url(url)
        self.token = token
        self.pwd = Path(str(sys.modules[self.__class__.__module__].__file__)).parent
        self._operation_name = Path(self.query_file).stem
        self._sku_subscription = self._load_query(self.query_file)

    def _normalize_graphql_url(self, url: str) -> str:
        parsed = urlsplit(url)
        path = parsed.path.rstrip("/")
        if path:
            return url
        return urlunsplit((parsed.scheme, parsed.netloc, "/graphql", parsed.query, parsed.fragment))

    async def __aexit__(self, exc_type, exc, tb):
        if self._subscription_session is not None and not self._subscription_session.closed:
            await self._subscription_session.close()
        self._subscription_session = None

    async def __aenter__(self) -> Self:
        return self

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is BlokliProvider:
                args = get_args(base)
                if args:
                    return_type = args[0]
                    if isinstance(return_type, type) and issubclass(return_type, JsonResponse):
                        cls._return_type = return_type
                    else:
                        raise TypeError(
                            "BlokliProvider return type must be a JsonResponse subclass"
                        )
                break

    #### PRIVATE METHODS ####
    def _request_headers(self, sse: bool = False) -> dict[str, str]:
        # Pin the schema version so a new server default can't silently change response shapes.
        headers: dict[str, str] = {"X-Blokli-Schema-Version": "1"}
        token = (self.token or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if sse:
            headers["Accept"] = "text/event-stream"
        return headers

    async def _ensure_subscription_session(self) -> aiohttp.ClientSession:
        if self._subscription_session is not None and not self._subscription_session.closed:
            return self._subscription_session

        self._subscription_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=None,
                connect=None,
                sock_connect=None,
                sock_read=None,
            )
        )
        return self._subscription_session

    def _load_query(self, path: str | Path) -> str:
        """
        Loads a graphql subscription from a file.
        :param path: Path to the file, relative to the provider's module.
        :return: The subscription as a string.
        """
        with open(self.pwd.joinpath(path)) as f:
            body = f.read().strip()

        if body.lower().startswith("subscription"):
            return body
        return f"subscription {{\n{body}\n}}"

    def _convert_response(self, response: dict) -> TBlokliResponse:
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

    async def subscribe(
        self, on_connect: Optional[Callable[[], None]] = None, **kwargs
    ) -> AsyncIterator[TBlokliResponse]:
        """
        Streams a blokli subscription, reconnecting on failure.
        :param on_connect: Called each time a connection is (re)established, before its first
            event. Subscriptions that start with a full snapshot resend it on every connection.
        :param kwargs: The variables to use in the subscription.
        """
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
                    outcome = "success" if response.status < 400 else "http_error"
                    BLOKLI_CALLS.labels(
                        "subscription",
                        self._operation_name,
                        outcome,
                    ).inc()
                    if response.status >= 400:
                        logger.error(
                            "Blokli subscription request failed",
                            {"status": response.status, "url": self.url},
                        )
                        raise ProviderError(f"Subscription failed with status {response.status}")

                    reconnect_delay_seconds = 1.0
                    SUBSCRIPTION_CONNECTED.labels(self._operation_name).set(1)
                    if on_connect is not None:
                        on_connect()
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
                            SUBSCRIPTION_LAST_EVENT.labels(self._operation_name).set(time.time())
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
                SUBSCRIPTION_CONNECTED.labels(self._operation_name).set(0)
                raise
            except Exception as error:
                BLOKLI_CALLS.labels(
                    "subscription",
                    self._operation_name,
                    type(error).__name__.lower(),
                ).inc()
                logger.warning(
                    "Blokli subscription interrupted, reconnecting",
                    {
                        "url": self.url,
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "retry_in_seconds": reconnect_delay_seconds,
                    },
                )

            SUBSCRIPTION_CONNECTED.labels(self._operation_name).set(0)
            await asyncio.sleep(reconnect_delay_seconds)
            reconnect_delay_seconds = min(
                reconnect_delay_seconds * 2,
                max_reconnect_delay_seconds,
            )
