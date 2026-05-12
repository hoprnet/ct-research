import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.api.response_objects import Session, SessionFailure
from core.types.balance import Balance
from core.types.message_format import MessageFormat
from core.components.node_helper import NodeHelper


@pytest.mark.asyncio
async def test_open_channel_calls_api_with_requested_amount():
    api = MagicMock()
    api.open_channel = AsyncMock(return_value=object())
    amount = Balance("1 wxHOPR")

    await NodeHelper.open_channel(api, "0xpeer", amount)

    api.open_channel.assert_awaited_once_with("0xpeer", amount)


@pytest.mark.asyncio
async def test_close_channel_returns_api_status():
    api = MagicMock()
    api.close_channel = AsyncMock(return_value=True)
    address = "peer-1"

    await NodeHelper.close_channel(api, address, "old_closed")

    api.close_channel.assert_awaited_once_with(address)


@pytest.mark.asyncio
async def test_fund_channel_calls_api_with_requested_amount():
    api = MagicMock()
    api.fund_channel = AsyncMock(return_value=True)
    address = "peer-1"
    amount = Balance("2 wxHOPR")

    await NodeHelper.fund_channel(api, address, amount)

    api.fund_channel.assert_awaited_once_with(address, amount)


@pytest.mark.asyncio
async def test_open_session_returns_session_on_success():
    api = MagicMock()
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9001,
            "protocol": "udp",
            "target": "0xdestination",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )
    api.post_udp_session = AsyncMock(return_value=session)

    opened = await NodeHelper.open_session(api, "0xdestination", "0xrelayer", "127.0.0.1")

    assert opened is session
    api.post_udp_session.assert_awaited_once_with("0xdestination", "0xrelayer", "127.0.0.1")


@pytest.mark.asyncio
async def test_open_session_returns_none_on_failure_response():
    api = MagicMock()
    api.post_udp_session = AsyncMock(
        return_value=SessionFailure(
            {
                "status": "FAILED",
                "error": "broken",
                "destination": "0xdestination",
                "relayer": "0xrelayer",
            }
        )
    )

    opened = await NodeHelper.open_session(api, "0xdestination", "0xrelayer", "127.0.0.1")

    assert opened is None


@pytest.mark.asyncio
async def test_close_session_returns_api_result():
    api = MagicMock()
    api.close_session = AsyncMock(return_value=False)
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9001,
            "protocol": "udp",
            "target": "0xdestination",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )

    closed = await NodeHelper.close_session(api, session, "0xrelayer")

    assert closed is False
    api.close_session.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_send_batch_messages_sends_full_batch_and_receives():
    session = MagicMock()
    session.send = MagicMock()
    session.receive = AsyncMock(return_value=300)

    message = MessageFormat("peer_1", "sender", 100, 3)
    message.queued_at = time.time() - 0.01

    await NodeHelper.send_batch_messages(session, message)

    assert session.send.call_count == message.batch_size
    session.receive.assert_awaited_once_with(
        message.packet_size,
        message.batch_size * message.packet_size,
    )


@pytest.mark.asyncio
async def test_send_batch_messages_raises_session_closed():
    session = MagicMock()
    session.send = MagicMock(side_effect=AttributeError("Socket is None for session on port 1"))
    session.receive = AsyncMock()

    message = MessageFormat("peer_1", "sender", 100, 3)

    with pytest.raises(AttributeError):
        await NodeHelper.send_batch_messages(session, message)

    session.receive.assert_not_called()


@pytest.mark.asyncio
async def test_send_batch_messages_raises_timeout():
    session = MagicMock()
    session.send = MagicMock()
    session.receive = AsyncMock(side_effect=asyncio.TimeoutError())

    message = MessageFormat("peer_1", "sender", 100, 2)

    with pytest.raises(asyncio.TimeoutError):
        await NodeHelper.send_batch_messages(session, message)

    assert session.send.call_count == message.batch_size


@pytest.mark.asyncio
async def test_send_batch_messages_raises_socket_error():
    session = MagicMock()
    session.send = MagicMock(side_effect=OSError("socket exploded"))
    session.receive = AsyncMock()

    message = MessageFormat("peer_1", "sender", 100, 2)

    with pytest.raises(OSError):
        await NodeHelper.send_batch_messages(session, message)

    session.receive.assert_not_called()
