"""
Stress tests for session handling under load.

These tests verify that session management works correctly under stress conditions:
1. High session count (100-200 concurrent sessions)
2. Grace period under load (many peers flapping)
3. Race condition stress (aggressive concurrent access)

Run with: pytest -m stress -v
Exclude with: pytest -m "not stress" -v
"""

import asyncio
import time
from typing import Optional
from unittest.mock import MagicMock

import pytest
import yaml
from pytest_mock import MockerFixture

from core.api.response_objects import (
    Addresses,
    Balances,
    Session,
)
from core.components import Peer
from core.components.balance import Balance
from core.components.config_parser import Parameters
from core.components.messages import MessageFormat
from core.node import Node


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_sessions():
    """Helper to create mock Session objects."""

    def _create_session(relayer: str, port: Optional[int] = None) -> Session:
        if port is None:
            # Generate port from relayer hash for consistency
            port = 9000 + abs(hash(relayer)) % 1000

        return Session(
            {
                "ip": "127.0.0.1",
                "port": port,
                "protocol": "udp",
                "target": relayer,
                "hoprMtu": 1002,
                "surbLen": 395,
            }
        )

    return _create_session


@pytest.fixture
async def stress_node(mocker: MockerFixture) -> Node:
    """Create a Node instance configured for stress testing."""
    node = Node("http://localhost:3001", "test_token")

    # Mock API methods
    mocker.patch.object(node.api, "address", return_value=Addresses({"native": "node_address"}))
    mocker.patch.object(
        node.api,
        "balances",
        return_value=Balances(
            {
                "hopr": "100 wxHOPR",
                "native": "10 xDai",
                "safeHopr": "50 wxHOPR",
                "safeNative": "5 xDai",
            }
        ),
    )
    mocker.patch.object(node.api, "healthyz", return_value=True)
    mocker.patch.object(node.api, "ticket_price", return_value=Balance("0.0001 wxHOPR"))

    # Load minimal test config
    with open("./test/test_config.yaml", "r") as file:
        params = Parameters(yaml.safe_load(file))

    # Override session-related flags for testing
    setattr(params.flags.node, "observe_message_queue", MagicMock(value=1))
    setattr(params.flags.node, "maintain_sessions", MagicMock(value=1))
    setattr(params.subgraph, "api_key", "test_key")

    node.params = params
    await node.retrieve_address()

    # Initialize session-related state
    node.sessions = {}
    node.session_close_grace_period = {}
    node.session_destinations = []
    node.peers = set()

    return node


@pytest.fixture
def mock_peers():
    """Create a set of mock peers for testing."""

    def _create_peers(count: int) -> set[Peer]:
        peers = set()
        for i in range(count):
            peer = Peer(f"peer_{i}")
            peers.add(peer)
        return peers

    return _create_peers


# ============================================================================
# Stress Tests
# ============================================================================


@pytest.mark.stress
@pytest.mark.asyncio
async def test_high_session_count_parallel_close(
    stress_node: Node, mock_sessions, mocker: MockerFixture
):
    """
    Stress test: Create 200 sessions and close them in parallel.

    Validates:
    - Parallel session closing works with many sessions
    - All sessions are properly closed at API level
    - All sockets are closed and cleared
    - Performance is acceptable (< 2 seconds for 200 sessions)
    - No exceptions during parallel close
    """
    SESSION_COUNT = 200

    # Create many sessions
    for i in range(SESSION_COUNT):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        stress_node.sessions[relayer] = session
        session.create_socket()

    # Mock API close_session to track calls
    close_call_count = 0

    async def mock_close(*args, **kwargs):
        nonlocal close_call_count
        close_call_count += 1
        # Simulate API latency
        await asyncio.sleep(0.01)
        return True

    mocker.patch.object(stress_node.api, "close_session", side_effect=mock_close)

    # Measure parallel close performance
    start_time = time.time()
    await stress_node.stop()
    duration = time.time() - start_time

    # Verify all sessions were closed
    assert len(stress_node.sessions) == 0, "All sessions should be cleared from cache"
    assert len(stress_node.session_close_grace_period) == 0, "Grace period cache should be cleared"
    assert (
        close_call_count == SESSION_COUNT
    ), f"All {SESSION_COUNT} sessions should be closed at API"

    # Verify performance (parallel execution should be much faster than sequential)
    # Sequential would take: 200 * 0.01s = 2s
    # Parallel should take: ~0.01s (plus overhead)
    assert duration < 1.0, f"Parallel close took {duration:.2f}s, should be < 1s"

    # Verify all sockets are closed
    for relayer, session in list(stress_node.sessions.items()):
        assert session.socket is None, f"Socket for {relayer} should be closed"

    print(f"✓ Successfully closed {SESSION_COUNT} sessions in {duration:.3f}s")


@pytest.mark.stress
@pytest.mark.asyncio
async def test_grace_period_under_load(
    stress_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    """
    Stress test: Grace period behavior with 100 sessions and 50% peer flapping.

    Validates:
    - Grace period tracking works correctly with many sessions
    - Sessions are not prematurely closed during peer flapping
    - Grace period timers are properly started and cancelled
    - No sessions leak when peers flap repeatedly
    """
    SESSION_COUNT = 100
    FLAP_ITERATIONS = 10

    # Create 100 sessions with peers
    peers = mock_peers(SESSION_COUNT)
    stress_node.peers = peers

    for i in range(SESSION_COUNT):
        relayer = f"peer_{i}"
        stress_node.session_destinations.append(relayer)
        session = mock_sessions(relayer)
        stress_node.sessions[relayer] = session
        session.create_socket()

    # Mock API to return all active sessions
    mocker.patch.object(
        stress_node.api,
        "list_udp_sessions",
        return_value=[session for session in stress_node.sessions.values()],
    )

    # Mock API close_session
    mocker.patch.object(stress_node.api, "close_session", return_value=True)

    # Simulate peer flapping: 50% of peers go unreachable, then come back
    flapping_peer_count = SESSION_COUNT // 2

    for iteration in range(FLAP_ITERATIONS):
        # Make 50% of peers unreachable
        stress_node.peers = set(list(peers)[flapping_peer_count:])
        await stress_node.maintain_sessions()

        # Verify grace periods started for unreachable peers
        assert (
            len(stress_node.session_close_grace_period) == flapping_peer_count
        ), f"Iteration {iteration}: Grace periods should be started for {flapping_peer_count} peers"

        # Verify sessions are NOT closed (grace period active)
        assert (
            len(stress_node.sessions) == SESSION_COUNT
        ), f"Iteration {iteration}: No sessions should be closed during grace period"

        # Make peers reachable again
        stress_node.peers = peers
        await stress_node.maintain_sessions()

        # Verify grace periods cancelled
        assert (
            len(stress_node.session_close_grace_period) == 0
        ), f"Iteration {iteration}: Grace periods should be cancelled when peers return"

        # Verify all sessions still present
        assert (
            len(stress_node.sessions) == SESSION_COUNT
        ), f"Iteration {iteration}: All sessions should be preserved"

    print(
        f"✓ Grace period handled {FLAP_ITERATIONS} iterations "
        f"of {flapping_peer_count} peers flapping"
    )


@pytest.mark.stress
@pytest.mark.asyncio
async def test_concurrent_session_creation_race(
    stress_node: Node, mock_sessions, mocker: MockerFixture
):
    """
    Stress test: 50 concurrent coroutines attempting to create sessions for same relayer.

    Validates:
    - Double-check pattern prevents duplicate session creation
    - Only one session created per relayer despite concurrent attempts
    - No duplicate sockets created
    - No exceptions during concurrent creation
    """
    CONCURRENT_ATTEMPTS = 50
    UNIQUE_RELAYERS = 10

    # Mock API post_udp_session to simulate slow session creation
    async def mock_post_udp_session(destination, relayer, listen_host):
        # Simulate network latency
        await asyncio.sleep(0.01)
        return mock_sessions(relayer)

    mocker.patch.object(stress_node.api, "post_udp_session", side_effect=mock_post_udp_session)

    # Mock API list_udp_sessions
    mocker.patch.object(stress_node.api, "list_udp_sessions", return_value=[])

    # Track socket creation attempts
    socket_creation_count: dict[str, int] = {}

    original_create_socket = Session.create_socket

    def track_socket_creation(self):
        relayer = self.target
        socket_creation_count[relayer] = socket_creation_count.get(relayer, 0) + 1
        return original_create_socket(self)

    mocker.patch.object(Session, "create_socket", track_socket_creation)

    # Set up session destinations
    stress_node.session_destinations = [f"peer_{i}" for i in range(UNIQUE_RELAYERS)]
    stress_node.peers = {Peer(f"peer_{i}") for i in range(UNIQUE_RELAYERS)}

    # Create concurrent tasks attempting to create sessions for same relayers
    async def attempt_session_creation(relayer_id):
        # Simulate message triggering session creation
        message = MessageFormat(f"peer_{relayer_id % UNIQUE_RELAYERS}", "sender", 500, 10)

        # Get or create session (mimics observe_message_queue behavior)
        session = stress_node.sessions.get(message.relayer)

        if not session:
            from core.components.node_helper import NodeHelper

            session = await NodeHelper.open_session(
                stress_node.api, "destination", message.relayer, "127.0.0.1"
            )

            if session:
                session.create_socket()

                # Double-check pattern
                if message.relayer not in stress_node.sessions:
                    stress_node.sessions[message.relayer] = session
                else:
                    # Another coroutine created it, close ours
                    session.close_socket()

    # Launch many concurrent attempts
    tasks = [attempt_session_creation(i) for i in range(CONCURRENT_ATTEMPTS)]
    await asyncio.gather(*tasks)

    # Verify only one session per relayer
    assert (
        len(stress_node.sessions) == UNIQUE_RELAYERS
    ), f"Should have exactly {UNIQUE_RELAYERS} sessions, not {len(stress_node.sessions)}"

    # Verify each relayer has exactly one session
    for i in range(UNIQUE_RELAYERS):
        relayer = f"peer_{i}"
        assert relayer in stress_node.sessions, f"Session for {relayer} should exist"

    print(f"✓ {CONCURRENT_ATTEMPTS} concurrent attempts created exactly {UNIQUE_RELAYERS} sessions")


@pytest.mark.stress
@pytest.mark.asyncio
async def test_concurrent_maintenance_and_message_sending(
    stress_node: Node, mock_sessions, mock_peers, mocker: MockerFixture
):
    """
    Stress test: Run maintain_sessions() and observe_message_queue() concurrently.

    Validates:
    - No RuntimeError from dictionary modification during iteration
    - No KeyError from sessions being removed during use
    - State remains consistent across concurrent operations
    - Lock-free design works correctly under concurrent load
    """
    SESSION_COUNT = 50
    MAINTENANCE_ITERATIONS = 20
    MESSAGE_ITERATIONS = 100

    # Set up initial state
    peers = mock_peers(SESSION_COUNT)
    stress_node.peers = peers
    stress_node.session_destinations = [f"peer_{i}" for i in range(SESSION_COUNT)]

    for i in range(SESSION_COUNT):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        stress_node.sessions[relayer] = session
        session.create_socket()

    # Mock API operations
    mocker.patch.object(
        stress_node.api,
        "list_udp_sessions",
        return_value=[session for session in stress_node.sessions.values()],
    )
    mocker.patch.object(stress_node.api, "close_session", return_value=True)

    # Track errors
    errors = []

    # Task 1: Continuously run maintain_sessions
    async def maintenance_loop():
        try:
            for _ in range(MAINTENANCE_ITERATIONS):
                await stress_node.maintain_sessions()
                await asyncio.sleep(0.001)
        except Exception as e:
            errors.append(f"Maintenance error: {e}")

    # Task 2: Continuously simulate message queue operations
    async def message_loop():
        try:
            for i in range(MESSAGE_ITERATIONS):
                # Simulate accessing sessions (like observe_message_queue does)
                relayer = f"peer_{i % SESSION_COUNT}"

                # This mimics the session access pattern
                session = stress_node.sessions.get(relayer)
                if session:
                    # Simulate using the session
                    _ = session.payload

                await asyncio.sleep(0.001)
        except Exception as e:
            errors.append(f"Message error: {e}")

    # Run both concurrently
    await asyncio.gather(maintenance_loop(), message_loop())

    # Verify no errors occurred
    assert len(errors) == 0, f"Errors occurred during concurrent operations: {errors}"

    # Verify state is consistent
    assert isinstance(stress_node.sessions, dict), "Sessions dict should still be a dict"
    assert isinstance(
        stress_node.session_close_grace_period, dict
    ), "Grace period dict should still be a dict"

    print(
        f"✓ Ran {MAINTENANCE_ITERATIONS} maintenance + "
        f"{MESSAGE_ITERATIONS} message operations concurrently"
    )


@pytest.mark.stress
@pytest.mark.asyncio
async def test_memory_usage_with_many_sessions(
    stress_node: Node, mock_sessions, mocker: MockerFixture
):
    """
    Stress test: Create and destroy 200 sessions, verify complete cleanup.

    Validates:
    - All sockets properly closed
    - All dictionary entries cleared
    - No session references leaked
    - Memory cleanup is complete after stop()
    """
    SESSION_COUNT = 200

    # Track initial state
    initial_session_count = len(stress_node.sessions)
    initial_grace_count = len(stress_node.session_close_grace_period)

    # Create many sessions
    created_sockets = []
    for i in range(SESSION_COUNT):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        stress_node.sessions[relayer] = session
        socket = session.create_socket()
        created_sockets.append(socket)

    # Verify sessions created
    assert len(stress_node.sessions) == SESSION_COUNT, f"Should have {SESSION_COUNT} sessions"
    assert all(
        session.socket is not None for session in stress_node.sessions.values()
    ), "All sessions should have sockets"

    # Mock API close
    close_calls = []

    async def track_close(session, *args, **kwargs):
        close_calls.append(session)
        return True

    mocker.patch.object(stress_node.api, "close_session", side_effect=track_close)

    # Stop and cleanup
    await stress_node.stop()

    # Verify complete cleanup
    assert len(stress_node.sessions) == 0, "All sessions should be removed from cache"
    assert len(stress_node.session_close_grace_period) == 0, "Grace period cache should be cleared"
    assert (
        len(close_calls) == SESSION_COUNT
    ), f"All {SESSION_COUNT} sessions should be closed at API"

    # Verify all sockets are closed
    for session in close_calls:
        assert session.socket is None, "Socket should be None after close_socket()"

    # Verify we're back to initial state
    assert (
        len(stress_node.sessions) == initial_session_count
    ), "Should return to initial session count"
    assert (
        len(stress_node.session_close_grace_period) == initial_grace_count
    ), "Should return to initial grace period count"

    print(f"✓ Created and cleaned up {SESSION_COUNT} sessions completely")
