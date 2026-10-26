import asyncio
from typing import Any, cast
from unittest.mock import Mock

import pytest

from core.api import session as session_module
from core.api.response_objects import Session
from core.types.message_format import MessageFormat


class FakeLoop:
    def __init__(self, side_effects):
        self._side_effects = iter(side_effects)

    async def sock_recvfrom(self, sock, size):
        effect = next(self._side_effects)
        if isinstance(effect, Exception):
            raise effect
        return effect


def build_session() -> Session:
    return Session(
        {
            "ip": "127.0.0.1",
            "port": 9100,
            "protocol": "udp",
            "target": "peer",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )


def test_close_socket_clears_reference_on_oserror():
    session = build_session()
    failing_socket = Mock()
    failing_socket.close.side_effect = OSError("already closed")
    session.socket = failing_socket

    session.close_socket()

    assert session.socket is None


def test_close_socket_propagates_unexpected_failures():
    session = build_session()
    failing_socket = Mock()
    failing_socket.close.side_effect = RuntimeError("boom")
    session.socket = failing_socket

    with pytest.raises(RuntimeError, match="boom"):
        session.close_socket()

    assert session.socket is failing_socket


def test_send_returns_zero_when_socket_would_block():
    session = build_session()
    blocking_socket = Mock()
    blocking_socket.sendto.side_effect = BlockingIOError()
    session.socket = blocking_socket

    assert session.send(b"payload") == 0


@pytest.mark.asyncio
async def test_receive_returns_partial_bytes_on_connection_reset(monkeypatch):
    session = build_session()
    session.socket = cast(Any, object())
    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: FakeLoop([(b"abc", ("127.0.0.1", 9100)), ConnectionResetError()]),
    )

    received = await session.receive(chunk_size=8, total_size=6)

    assert received == 3


@pytest.mark.asyncio
async def test_receive_returns_size_for_undecodable_payload(monkeypatch):
    session = build_session()
    session.socket = cast(Any, object())
    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: FakeLoop([(b"\xff\xfe\xfd", ("127.0.0.1", 9100))]),
    )

    received = await session.receive(chunk_size=8, total_size=3)

    assert received == 3


class ClockedLoop:
    """Returns each datagram at its own time, moving the clock `receive` reads the RTT from."""

    def __init__(self, datagrams: list[tuple[float, bytes]], monkeypatch):
        self._datagrams = iter(datagrams)
        self._now = 0.0
        monkeypatch.setattr(session_module.time, "time", lambda: self._now)

    async def sock_recvfrom(self, sock, size):
        self._now, data = next(self._datagrams)
        return data, ("127.0.0.1", 9100)


def echo(timestamp_ms: int) -> bytes:
    return MessageFormat("0xrelayer", "0xsender", packet_size=200, timestamp=timestamp_ms).bytes()


@pytest.mark.asyncio
async def test_receive_measures_rtt_when_each_echo_arrives(monkeypatch):
    session = build_session()
    session.socket = cast(Any, object())
    first, second = echo(1000), echo(1000)
    loop = ClockedLoop([(2.0, first), (5.0, second)], monkeypatch)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    rtt = Mock()
    monkeypatch.setattr(session_module, "MESSAGES_RTT", rtt)

    received = await session.receive(chunk_size=200, total_size=len(first) + len(second))

    assert received == len(first) + len(second)
    assert [c.args[0] for c in rtt.labels.return_value.observe.call_args_list] == [1.0, 4.0]


@pytest.mark.asyncio
async def test_receive_records_a_message_split_across_datagrams_once(monkeypatch):
    session = build_session()
    session.socket = cast(Any, object())
    payload = echo(1000)
    loop = ClockedLoop([(2.0, payload[:10]), (3.0, payload[10:])], monkeypatch)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    rtt = Mock()
    monkeypatch.setattr(session_module, "MESSAGES_RTT", rtt)

    received = await session.receive(chunk_size=200, total_size=len(payload))

    assert received == len(payload)
    assert [c.args[0] for c in rtt.labels.return_value.observe.call_args_list] == [2.0]


@pytest.mark.asyncio
async def test_receive_skips_invalid_message_fragments(monkeypatch):
    session = build_session()
    session.socket = cast(Any, object())
    monkeypatch.setattr(
        asyncio,
        "get_running_loop",
        lambda: FakeLoop([(b"not-a-message\0still-bad", ("127.0.0.1", 9100))]),
    )

    payload = b"not-a-message\0still-bad"
    received = await session.receive(chunk_size=64, total_size=len(payload))

    assert received == len(payload)
