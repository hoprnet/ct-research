import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from core.types.message_format import MessageFormat
from core.node import Node


@pytest.mark.asyncio
async def test_session_closed_when_peer_temporarily_unreachable(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(
        session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[session])
    )
    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(return_value=True))

    session_node.peers = {a: p for a, p in mock_peers.items() if p.address.native != relayer}

    await session_node.maintain_sessions()

    assert relayer in session_node.sessions
    assert session.socket is not None


@pytest.mark.asyncio
async def test_session_persists_with_grace_period(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_2"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(
        session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[session])
    )
    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(return_value=True))

    session_node.peers = {a: p for a, p in mock_peers.items() if p.address.native != relayer}

    for _ in range(3):
        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    session_node.peers = mock_peers
    await session_node.maintain_sessions()

    assert relayer in session_node.sessions


@pytest.mark.asyncio
async def test_reachable_peer_clears_existing_grace_period(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_2"
    session = mock_sessions(relayer)
    session.create_socket()

    session_node.sessions[relayer] = session
    session_node.peers = mock_peers
    session_node.session_close_grace_period[relayer] = 1.0

    mocker.patch.object(
        session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[session])
    )
    close_session = AsyncMock(return_value=True)
    mocker.patch.object(session_node.api, "close_session", new=close_session)

    await session_node.maintain_sessions()

    assert relayer not in session_node.session_close_grace_period
    close_session.assert_not_called()


@pytest.mark.asyncio
async def test_peer_quality_flapping_causes_session_churn(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_3"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(
        session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[session])
    )
    close_count = 0

    async def track_close(*args, **kwargs):
        nonlocal close_count
        close_count += 1
        return True

    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(side_effect=track_close))

    for available in [True, False, True, False, True, False]:
        if available:
            session_node.peers = mock_peers
        else:
            session_node.peers = {
                a: p for a, p in mock_peers.items() if p.address.native != relayer
            }

        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    assert close_count <= 1


@pytest.mark.asyncio
async def test_session_is_preserved_when_udp_session_list_is_unavailable(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)
    session.create_socket()
    session_node.sessions[relayer] = session
    session_node.peers = mock_peers

    close_session = AsyncMock(return_value=True)
    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=None))
    mocker.patch.object(session_node.api, "close_session", new=close_session)

    await session_node.maintain_sessions()

    assert relayer in session_node.sessions
    assert session.socket is not None
    close_session.assert_not_called()


@pytest.mark.asyncio
async def test_dictionary_changed_during_iteration(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    for i in range(5):
        relayer = f"peer_{i}"
        session_node.sessions[relayer] = mock_sessions(relayer)

    session_node.peers = mock_peers

    mocker.patch.object(
        session_node.api,
        "list_udp_sessions",
        return_value=list(session_node.sessions.values()),
    )

    iteration_errors = []

    async def add_sessions_during_iteration():
        for i in range(10, 20):
            try:
                session_node.sessions[f"peer_{i}"] = mock_sessions(f"peer_{i}")
                await asyncio.sleep(0.001)
            except RuntimeError as err:
                iteration_errors.append(err)

    async def iterate_sessions():
        for _ in range(10):
            try:
                await session_node.maintain_sessions()
                await asyncio.sleep(0.001)
            except RuntimeError as err:
                iteration_errors.append(err)

    await asyncio.gather(
        add_sessions_during_iteration(), iterate_sessions(), return_exceptions=True
    )

    dict_changed_errors = [err for err in iteration_errors if "dictionary" in str(err).lower()]
    assert len(dict_changed_errors) == 0


@pytest.mark.asyncio
async def test_session_used_after_removal(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[]))
    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(return_value=True))

    original_socket = session.socket
    await session_node.maintain_sessions()

    assert relayer not in session_node.sessions
    assert original_socket is not None
    assert session.socket is None


@pytest.mark.asyncio
async def test_sessions_accumulate_when_cleanup_disabled(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[]))
    close_session = AsyncMock(return_value=False)
    mocker.patch.object(session_node.api, "close_session", new=close_session)

    for i in range(10):
        session_node.sessions[f"peer_{i}"] = mock_sessions(f"peer_{i}")

    session_node.peers = {}

    for _ in range(5):
        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    assert len(session_node.sessions) == 10
    assert close_session.await_count == 50


@pytest.mark.asyncio
async def test_orphaned_sessions_after_api_close_failure(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = {}
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[]))

    close_called = False

    async def failing_close(*args, **kwargs):
        nonlocal close_called
        close_called = True
        return False

    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(side_effect=failing_close))

    await session_node.maintain_sessions()

    assert close_called
    assert relayer in session_node.sessions
    assert session_node.sessions[relayer] is session
    assert session.socket is not None


@pytest.mark.asyncio
async def test_session_is_preserved_when_api_close_raises(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_2"
    session = mock_sessions(relayer)
    session_node.peers = {}
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[]))
    mocker.patch.object(
        session_node.api,
        "close_session",
        new=AsyncMock(side_effect=RuntimeError("close exploded")),
    )

    await session_node.maintain_sessions()

    assert relayer in session_node.sessions
    assert session_node.sessions[relayer] is session
    assert session.socket is not None


@pytest.mark.asyncio
async def test_sessions_not_cleaned_on_node_stop(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    for i in range(5):
        session = mock_sessions(f"peer_{i}")
        session_node.sessions[f"peer_{i}"] = session
        session.create_socket()

    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(return_value=True))

    await session_node.stop()

    assert len(session_node.sessions) == 0
    assert len([s for s in session_node.sessions.values() if s.socket is not None]) == 0


@pytest.mark.asyncio
async def test_stop_preserves_sessions_that_fail_api_close(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    failed_relayer = "peer_failed"
    successful_relayer = "peer_ok"

    failed_session = mock_sessions(failed_relayer, port=9301)
    successful_session = mock_sessions(successful_relayer, port=9302)
    failed_session.create_socket()
    successful_session.create_socket()

    session_node.sessions[failed_relayer] = failed_session
    session_node.sessions[successful_relayer] = successful_session

    async def close_by_port(session):
        return session.port != failed_session.port

    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(side_effect=close_by_port))

    await session_node.stop()

    assert successful_relayer not in session_node.sessions
    assert failed_relayer in session_node.sessions
    assert session_node.sessions[failed_relayer] is failed_session
    assert failed_session.socket is not None


@pytest.mark.asyncio
async def test_maintain_sessions_defers_cleanup_while_send_is_in_flight(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)
    session.create_socket()
    session_node.sessions[relayer] = session
    session_node.peers = {}

    task = asyncio.create_task(asyncio.sleep(0.05))
    session_node._track_in_flight_message_task(session, task)

    mocker.patch.object(session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[]))
    close_session = AsyncMock(return_value=True)
    mocker.patch.object(session_node.api, "close_session", new=close_session)

    await session_node.maintain_sessions()

    assert relayer in session_node.sessions
    assert session.socket is not None
    close_session.assert_not_called()

    await task
    await session_node.maintain_sessions()

    assert relayer not in session_node.sessions
    close_session.assert_called_once()


@pytest.mark.asyncio
async def test_stop_waits_for_in_flight_messages(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)
    session.create_socket()
    session_node.sessions[relayer] = session

    send_gate = asyncio.Event()
    send_task = asyncio.create_task(send_gate.wait())
    session_node._track_in_flight_message_task(session, send_task)

    close_started = False

    async def track_close(_session):
        nonlocal close_started
        close_started = True
        return True

    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(side_effect=track_close))

    stop_task = asyncio.create_task(session_node.stop())
    await asyncio.sleep(0.01)

    assert not close_started

    send_gate.set()
    await asyncio.wait_for(stop_task, timeout=1.0)

    assert close_started


@pytest.mark.asyncio
async def test_in_flight_messages_lost_on_shutdown(session_node: Node, mock_sessions):
    relayer = "peer_1"
    session = mock_sessions(relayer)
    session_node.sessions[relayer] = session
    session.create_socket()

    send_called = False
    original_send = session.send

    def track_send(*args, **kwargs):
        nonlocal send_called
        send_called = True
        return original_send(*args, **kwargs)

    session.send = track_send

    message = MessageFormat(relayer, "sender", 500, 10)
    asyncio.create_task(asyncio.to_thread(session.send, message))

    await asyncio.sleep(0.01)
    await session_node.stop()
    await asyncio.sleep(0.01)

    assert session_node.running is False
    assert send_called
