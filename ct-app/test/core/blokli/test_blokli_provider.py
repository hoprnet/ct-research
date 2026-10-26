import pytest

from core.blokli.entries import BlokliTicketParameters
from core.blokli.providers import TicketParametersSubscription


def test_subscription_query_uses_explicit_subscription_document_when_provided():
    provider = TicketParametersSubscription("http://blokli.local")

    assert provider._sku_subscription.startswith("subscription")
    assert "ticketParametersUpdated" in provider._sku_subscription


def test_parse_sse_event_data_returns_payload_dict():
    provider = TicketParametersSubscription("http://blokli.local")
    payload = '{"data":{"ticketParametersUpdated":{"ticketPrice":"3 wxHOPR"}}}'

    parsed = provider._parse_sse_event_data(["event: next", f"data: {payload}"])

    assert parsed is not None
    assert parsed["ticketParametersUpdated"]["ticketPrice"] == "3 wxHOPR"


def test_parse_sse_event_data_returns_none_for_invalid_json():
    provider = TicketParametersSubscription("http://blokli.local")

    parsed = provider._parse_sse_event_data(["data: {invalid-json"])

    assert parsed is None


def test_subscription_payload_is_converted_to_typed_response():
    provider = TicketParametersSubscription("http://blokli.local")
    response = {
        "ticketParametersUpdated": {
            "ticketPrice": "5 wxHOPR",
            "minTicketWinningProbability": 0.5,
        }
    }

    converted = provider._convert_response(response)

    assert isinstance(converted, BlokliTicketParameters)
    assert converted.ticket_price.as_str == "5 wxHOPR"
    assert converted.min_ticket_winning_probability == 0.5


def test_request_headers_do_not_include_authorization_when_token_empty():
    provider = TicketParametersSubscription("http://blokli.local", token="")

    headers = provider._request_headers()

    assert "Authorization" not in headers


def test_request_headers_include_authorization_when_token_present():
    provider = TicketParametersSubscription("http://blokli.local", token="secret")

    headers = provider._request_headers()

    assert headers["Authorization"] == "Bearer secret"


def test_provider_normalizes_root_url_to_graphql_path():
    assert TicketParametersSubscription("http://blokli.local").url == "http://blokli.local/graphql"
    assert (
        TicketParametersSubscription("http://blokli.local/graphql").url
        == "http://blokli.local/graphql"
    )


@pytest.mark.asyncio
async def test_subscription_session_uses_no_timeout():
    provider = TicketParametersSubscription("http://blokli.local")

    session = await provider._ensure_subscription_session()

    assert session.timeout.total is None
    await session.close()


@pytest.mark.asyncio
async def test_subscription_session_reuses_open_session():
    provider = TicketParametersSubscription("http://blokli.local")

    session_one = await provider._ensure_subscription_session()
    session_two = await provider._ensure_subscription_session()

    assert session_one is session_two
    await session_one.close()


@pytest.mark.asyncio
async def test_context_manager_keeps_sessions_lazy_until_operation():
    provider = TicketParametersSubscription("http://blokli.local")

    async with provider as client:
        assert client._subscription_session is None

        session = await client._ensure_subscription_session()

        assert client._subscription_session == session


class _FakeContent:
    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    def at_eof(self) -> bool:
        return not self._lines

    async def readline(self) -> bytes:
        return self._lines.pop(0) if self._lines else b""


class _FakeResponse:
    status = 200

    def __init__(self, lines: list[bytes]):
        self.content = _FakeContent(lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    closed = False

    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def post(self, *args, **kwargs):
        return _FakeResponse(self._lines)


@pytest.mark.asyncio
async def test_subscription_reports_connection_and_last_event(mocker):
    import asyncio
    from unittest.mock import AsyncMock

    from core.blokli.blokli_provider import SUBSCRIPTION_CONNECTED, SUBSCRIPTION_LAST_EVENT

    payload = (
        b'data: {"data":{"ticketParametersUpdated":'
        b'{"minTicketWinningProbability":0.5,"ticketPrice":"1 wxHOPR"}}}\n'
    )
    provider = TicketParametersSubscription("http://blokli.local")
    mocker.patch.object(
        provider,
        "_ensure_subscription_session",
        new=AsyncMock(return_value=_FakeSession([b"event: next\n", payload, b"\n"])),
    )
    # Stop the reconnect loop once the stream has ended.
    mocker.patch(
        "core.blokli.blokli_provider.asyncio.sleep",
        new=AsyncMock(side_effect=asyncio.CancelledError),
    )
    connected = SUBSCRIPTION_CONNECTED.labels(provider._operation_name)
    connects: list[int] = []

    stream = provider.subscribe(on_connect=lambda: connects.append(1))
    event = await stream.__anext__()

    assert event.min_ticket_winning_probability == 0.5
    assert connects == [1]
    assert connected._value.get() == 1
    assert SUBSCRIPTION_LAST_EVENT.labels(provider._operation_name)._value.get() > 0

    with pytest.raises(asyncio.CancelledError):
        await stream.__anext__()
    assert connected._value.get() == 0
