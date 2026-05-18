import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from core.api.response_objects import Session
from core.types.asyncloop import AsyncLoop
from core.types.peer import Peer
from core.types.message_format import MessageFormat
from core.types.message_queue import MessageQueue
from core.messages.message_metrics import (
    BATCH_SCHEDULE_FAILURES,
    MESSAGE_REQUEUES,
    SESSION_OPEN_EVENTS,
    WORKER_LOOP_EVENTS,
)
from core.components.node_helper import NodeHelper
from core.node import Node


def _counter_value(metric, **labels) -> float:
    if labels:
        return metric.labels(**labels)._value.get()
    return metric._value.get()


@pytest.mark.asyncio
async def test_track_in_flight_message_task_cleans_up_after_completion(
    session_node: Node, mock_sessions
):
    session = mock_sessions("peer_0", port=9401)

    async def complete():
        await asyncio.sleep(0)

    task = asyncio.create_task(complete())
    session_node._track_in_flight_message_task(session, task)

    assert session_node._session_has_in_flight_tasks(session)

    await task
    await asyncio.sleep(0)

    assert not session_node._session_has_in_flight_tasks(session)
    assert task not in session_node._in_flight_message_tasks


@pytest.mark.asyncio
async def test_message_is_requeued_when_session_creation_fails(
    session_node: Node, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    relayer = "peer_1"
    exit_peer = "peer_exit"
    session_node.channels = MagicMock()
    session_node._cached_address_to_open_channel = {relayer: MagicMock()}
    session_node.peers = {relayer: Peer(relayer), exit_peer: Peer(exit_peer)}
    session_node.session_destinations = [relayer, exit_peer]

    message = MessageFormat(relayer, "sender", 500, 1)
    before = _counter_value(MESSAGE_REQUEUES, reason="session_unavailable")

    mocker.patch.object(session_node, "_get_or_create_session", new=AsyncMock(return_value=None))

    with caplog.at_level("DEBUG"):
        scheduled = await session_node._process_message(message, worker_id=0)

    assert not scheduled
    assert MessageQueue().buffer.qsize() == 1
    queued_message = await MessageQueue().get()
    assert queued_message is message
    assert _counter_value(MESSAGE_REQUEUES, reason="session_unavailable") == before + 1
    assert "Requeueing message for retry" in caplog.text


@pytest.mark.asyncio
async def test_message_is_requeued_when_no_destination_is_available(
    session_node: Node, mocker: MockerFixture
):
    relayer = "peer_1"
    session_node.channels = MagicMock()
    session_node._cached_address_to_open_channel = {relayer: MagicMock()}
    session_node.peers = {relayer: Peer(relayer)}
    session_node.session_destinations = [relayer]

    message = MessageFormat(relayer, "sender", 500, 1)
    create_session = mocker.patch.object(
        session_node, "_get_or_create_session", new=AsyncMock(return_value=None)
    )

    scheduled = await session_node._process_message(message, worker_id=0)

    assert not scheduled
    create_session.assert_not_called()
    assert MessageQueue().buffer.qsize() == 1
    queued_message = await MessageQueue().get()
    assert queued_message is message


@pytest.mark.asyncio
async def test_session_is_reused_even_when_destination_changes(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_4"
    old_session = mock_sessions(relayer, port=9101)
    old_session.target = "destination_a"
    old_session.create_socket()
    session_node.sessions[relayer] = old_session

    post_udp_session = mocker.patch.object(
        session_node.api,
        "post_udp_session",
        new=AsyncMock(),
    )
    close_session = mocker.patch.object(session_node.api, "close_session", new=AsyncMock())

    session = await session_node._get_or_create_session(relayer, "destination_b")

    assert session is old_session
    assert session_node.sessions[relayer] is old_session
    assert old_session.socket is not None
    post_udp_session.assert_not_called()
    close_session.assert_not_called()


@pytest.mark.asyncio
async def test_destination_change_does_not_attempt_retire_or_reopen(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_4"
    old_session = mock_sessions(relayer, port=9101)
    old_session.target = "destination_a"
    old_session.create_socket()
    session_node.sessions[relayer] = old_session

    post_udp_session = AsyncMock()
    mocker.patch.object(session_node.api, "post_udp_session", new=post_udp_session)
    close_session = mocker.patch.object(
        session_node.api, "close_session", new=AsyncMock(return_value=False)
    )

    session = await session_node._get_or_create_session(relayer, "destination_b")

    assert session is old_session
    assert session_node.sessions[relayer] is old_session
    assert old_session.socket is not None
    post_udp_session.assert_not_called()
    close_session.assert_not_called()


@pytest.mark.asyncio
async def test_retire_session_removes_cached_session_and_grace_period_on_success(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_5"
    session = mock_sessions(relayer, port=9402)
    session.create_socket()
    session_node.sessions[relayer] = session
    session_node.session_close_grace_period[relayer] = 123.0

    mocker.patch.object(NodeHelper, "close_session", new=AsyncMock(return_value=True))

    retired = await session_node._retire_session(
        relayer, session, reason="test", wait_for_in_flight=False
    )

    assert retired
    assert relayer not in session_node.sessions
    assert relayer not in session_node.session_close_grace_period
    assert session.socket is None


@pytest.mark.asyncio
async def test_get_or_create_session_respects_rate_limiter(
    session_node: Node, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    relayer = "peer_2"
    before = _counter_value(SESSION_OPEN_EVENTS, result="rate_limited")
    can_attempt = mocker.patch.object(
        session_node.session_rate_limiter,
        "can_attempt",
        return_value=(False, 3.5),
    )
    post_udp_session = mocker.patch.object(session_node.api, "post_udp_session", new=AsyncMock())

    with caplog.at_level("DEBUG"):
        session = await session_node._get_or_create_session(relayer, "destination_a")

    assert session is None
    can_attempt.assert_called_once_with(relayer)
    post_udp_session.assert_not_called()
    assert _counter_value(SESSION_OPEN_EVENTS, result="rate_limited") == before + 1
    assert "Session opening rate-limited" in caplog.text


@pytest.mark.asyncio
async def test_get_or_create_session_reuses_existing_matching_session(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_existing"
    before = _counter_value(SESSION_OPEN_EVENTS, result="reused_existing")
    session = mock_sessions(relayer, port=9403)
    session.target = "destination_a"
    session_node.sessions[relayer] = session
    post_udp_session = mocker.patch.object(session_node.api, "post_udp_session", new=AsyncMock())

    existing = await session_node._get_or_create_session(relayer, "destination_a")

    assert existing is session
    post_udp_session.assert_not_called()
    assert _counter_value(SESSION_OPEN_EVENTS, result="reused_existing") == before + 1


@pytest.mark.asyncio
async def test_schedule_message_batch_requeues_when_async_task_creation_fails(
    session_node: Node, mock_sessions, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    relayer = "peer_3"
    session_node.address = MagicMock(native="node_address")
    session_node.sessions[relayer] = mock_sessions(relayer, port=9201)
    message = MessageFormat(relayer, "sender", 500, 1)
    before = _counter_value(BATCH_SCHEDULE_FAILURES)

    mocker.patch.object(AsyncLoop, "add", return_value=None)

    with caplog.at_level("DEBUG"):
        scheduled = session_node._schedule_message_batch(message, relayer)

    assert not scheduled
    assert len(session_node._in_flight_message_tasks) == 0
    assert _counter_value(BATCH_SCHEDULE_FAILURES) == before + 1
    assert "Failed to schedule message batch" in caplog.text


@pytest.mark.asyncio
async def test_process_message_requeues_when_batch_scheduling_fails(
    session_node: Node, mock_sessions, mocker: MockerFixture
):
    relayer = "peer_7"
    session = mock_sessions(relayer, port=9404)
    session_node.channels = MagicMock()
    session_node._cached_address_to_open_channel = {relayer: MagicMock()}
    session_node.peers = {relayer: Peer(relayer), "exit_peer": Peer("exit_peer")}
    session_node.session_destinations = [relayer, "exit_peer"]

    message = MessageFormat(relayer, "sender", 500, 1)

    mocker.patch.object(session_node, "_get_or_create_session", new=AsyncMock(return_value=session))
    mocker.patch.object(session_node, "_schedule_message_batch", return_value=False)

    scheduled = await session_node._process_message(message, worker_id=0)

    assert not scheduled
    assert MessageQueue().buffer.qsize() == 1
    queued_message = await MessageQueue().get()
    assert queued_message is message


@pytest.mark.asyncio
async def test_process_message_requeues_after_rate_limit_delay(
    session_node: Node, mocker: MockerFixture
):
    relayer = "peer_rate_limited"
    exit_peer = "peer_exit"
    session_node.channels = MagicMock()
    session_node._cached_address_to_open_channel = {relayer: MagicMock()}
    session_node.peers = {relayer: Peer(relayer), exit_peer: Peer(exit_peer)}
    session_node.session_destinations = [relayer, exit_peer]
    session_node._session_retry_wait_seconds[relayer] = 0.05

    message = MessageFormat(relayer, "sender", 500, 1)
    mocker.patch.object(session_node, "_get_or_create_session", new=AsyncMock(return_value=None))

    scheduled = await session_node._process_message(message, worker_id=0)

    assert not scheduled
    assert MessageQueue().buffer.qsize() == 0
    await asyncio.sleep(0.07)
    assert MessageQueue().buffer.qsize() == 1
    queued_message = await MessageQueue().get()
    assert queued_message is message


@pytest.mark.asyncio
async def test_concurrent_session_creation_reuses_cached_session_and_closes_duplicate_socket(
    session_node: Node, mocker: MockerFixture
):
    relayer = "peer_6"
    before = _counter_value(SESSION_OPEN_EVENTS, result="opened")
    created_session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9301,
            "protocol": "udp",
            "target": "destination_a",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )

    async def open_session(*args, **kwargs):
        await asyncio.sleep(0)
        return created_session

    post_udp_session = mocker.patch.object(
        session_node.api,
        "post_udp_session",
        new=AsyncMock(side_effect=open_session),
    )

    first_task = asyncio.create_task(session_node._get_or_create_session(relayer, "destination_a"))
    second_task = asyncio.create_task(session_node._get_or_create_session(relayer, "destination_a"))

    first_session, second_session = await asyncio.gather(first_task, second_task)

    assert first_session is second_session
    assert first_session is created_session
    assert session_node.sessions[relayer] is created_session
    assert created_session.socket is not None
    assert post_udp_session.await_count == 1
    assert _counter_value(SESSION_OPEN_EVENTS, result="opened") == before + 1


@pytest.mark.asyncio
async def test_message_worker_records_timeout_event(
    session_node: Node, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
):
    before = _counter_value(WORKER_LOOP_EVENTS, event="timeout")

    async def raise_timeout(awaitable, timeout):
        awaitable.close()
        session_node.running = False
        raise asyncio.TimeoutError

    mocker.patch("core.mixins.session.workers.asyncio.wait_for", side_effect=raise_timeout)

    with caplog.at_level("DEBUG"):
        await session_node._message_worker(worker_id=7)

    assert _counter_value(WORKER_LOOP_EVENTS, event="timeout") == before + 1
    assert "Message worker 7 timed out waiting for work" in caplog.text


@pytest.mark.asyncio
async def test_concurrent_session_access_race_condition(
    session_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    relayer = "peer_1"
    session = mock_sessions(relayer)
    queue = MessageQueue()

    session_node.peers = mock_peers
    session_node.channels = MagicMock()
    session_node._cached_address_to_open_channel = {relayer: MagicMock()}
    session_node.session_destinations = [relayer, "peer_2"]

    mocker.patch.object(
        session_node.api, "list_udp_sessions", new=AsyncMock(return_value=[session])
    )
    mocker.patch.object(session_node.api, "close_session", new=AsyncMock(return_value=True))
    mocker.patch.object(session_node, "_get_or_create_session", new=AsyncMock(return_value=session))
    mocker.patch.object(session_node, "_schedule_message_batch", return_value=True)

    for _ in range(40):
        await queue.put(MessageFormat(relayer, "test_sender", 500, 10))

    exceptions = []
    observe_task = asyncio.create_task(session_node.observe_message_queue())

    async def run_maintain():
        for _ in range(20):
            try:
                session_node.peers = {} if len(session_node.sessions) > 2 else mock_peers
                await session_node.maintain_sessions()
            except Exception as err:
                exceptions.append(err)
            await asyncio.sleep(0.001)

    try:
        await asyncio.wait_for(run_maintain(), timeout=2.0)
    except asyncio.TimeoutError:
        pass

    session_node.running = False
    try:
        await asyncio.wait_for(observe_task, timeout=2.0)
    except asyncio.TimeoutError:
        observe_task.cancel()

    runtime_errors = [err for err in exceptions if isinstance(err, RuntimeError)]
    assert len(runtime_errors) == 0, (
        f"Race condition detected: {len(runtime_errors)} RuntimeError(s) occurred. "
        f"Errors: {runtime_errors[:3]}. "
        "Need to add locking to protect concurrent access to self.sessions"
    )
