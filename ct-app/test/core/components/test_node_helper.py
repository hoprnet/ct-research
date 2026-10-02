import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.api.response_objects import Session, SessionFailure
from core.components.node_helper import NodeHelper
from core.types.message_format import MessageFormat


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
    api.post_udp_session.assert_awaited_once_with(
        "0xdestination", relayer="0xrelayer", listen_host="127.0.0.1"
    )


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


def _burst_session(mtu: int = 1000, received: int | Exception = 0) -> MagicMock:
    session = MagicMock()
    session.mtu = mtu
    session.send = MagicMock(return_value=mtu)
    if isinstance(received, Exception):
        session.receive = AsyncMock(side_effect=received)
    else:
        session.receive = AsyncMock(return_value=received)
    return session


@pytest.mark.asyncio
async def test_send_burst_paces_packets_from_the_mtu_and_counts_echoes():
    # 0.16 Mbit/s over 1000-byte packets = 20 packets/s through the relayer, both directions
    # together, so the CT node sends 10 packets/s: 3 packets in 0.3 s.
    session = _burst_session(mtu=1000, received=2 * 600)
    message = MessageFormat("peer_1", "sender", 600)

    started_at = time.monotonic()
    result = await NodeHelper.send_burst(session, message, 0.16, 0.3, receive_timeout=7.5)
    elapsed = time.monotonic() - started_at

    assert session.send.call_count == 3
    assert result.sent == 3
    assert result.echoed == 2
    assert message.batch_size == 3
    # Packets are spread over the burst, not sent at once: the last one leaves at 0.2 s.
    assert elapsed >= 0.19
    session.receive.assert_awaited_once_with(600, 3 * 600, timeout=0.3 + 7.5)


@pytest.mark.asyncio
async def test_send_burst_does_not_count_unsent_packets_as_relayed():
    session = _burst_session(mtu=1000, received=10 * 600)
    session.send = MagicMock(side_effect=[1000, 0, 1000])
    message = MessageFormat("peer_1", "sender", 600)

    result = await NodeHelper.send_burst(session, message, 0.16, 0.3)

    assert result.sent == 2
    assert result.echoed == 2


@pytest.mark.asyncio
async def test_send_burst_raises_session_closed():
    session = _burst_session()
    session.send = MagicMock(side_effect=AttributeError("Socket is None for session on port 1"))
    message = MessageFormat("peer_1", "sender", 600)

    with pytest.raises(AttributeError):
        await NodeHelper.send_burst(session, message, 0.16, 0.3)


@pytest.mark.asyncio
async def test_send_burst_raises_timeout():
    session = _burst_session(received=asyncio.TimeoutError())
    message = MessageFormat("peer_1", "sender", 600)

    with pytest.raises(asyncio.TimeoutError):
        await NodeHelper.send_burst(session, message, 0.16, 0.1)

    assert session.send.call_count == 1


@pytest.mark.asyncio
async def test_send_burst_raises_socket_error():
    session = _burst_session()
    session.send = MagicMock(side_effect=OSError("socket exploded"))
    message = MessageFormat("peer_1", "sender", 600)

    with pytest.raises(OSError):
        await NodeHelper.send_burst(session, message, 0.16, 0.3)
