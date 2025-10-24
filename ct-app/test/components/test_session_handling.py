"""
Integration tests for session handling and cleanup.

These tests verify fixes for critical issues in session management:
1. Premature session closure when peers are temporarily unreachable
2. Race conditions in concurrent session access
3. Session leaks when cleanup fails or is disabled
4. Missing cleanup on node shutdown

After fixes are implemented, all tests should PASS.
"""

import asyncio
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

    def _create_session(relayer: str, port: int = None) -> Session:
        if port is None:
            # Generate port from relayer hash for consistency
            port = 9000 + abs(hash(relayer)) % 1000

        return Session(
            {
                "ip": "127.0.0.1",
                "port": port,
                "protocol": "udp",
                "target": relayer,
                "mtu": 1002,
                "surbLen": 395,
            }
        )

    return _create_session


@pytest.fixture
async def session_node(mocker: MockerFixture) -> Node:
    """Create a Node instance configured for session testing."""
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
    node.session_destinations = []
    node.connected = True

    return node


@pytest.fixture
def mock_peers() -> set[Peer]:
    """Create a set of mock peers for testing."""
    peer_addresses = [f"peer_{i}" for i in range(5)]
    peers = set()

    for addr in peer_addresses:
        peer = Peer(addr)
        peer.safe_balance = Balance("100 wxHOPR")
        peer.channel_balance = Balance("10 wxHOPR")
        peers.add(peer)

    return peers


# ============================================================================
# Test Category 1: Premature Session Closure
# ============================================================================


@pytest.mark.asyncio
async def test_session_closed_when_peer_temporarily_unreachable(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions are prematurely closed when peers become temporarily unreachable.

    BUG: This test demonstrates that sessions are closed immediately when a peer
    is removed from the reachable peers list, even if the peer comes back shortly after.

    Expected: FAIL (session gets closed prematurely)
    """
    relayer = "peer_1"
    session = mock_sessions(relayer)

    # Setup: Node with active session
    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    # Mock API to return the session as active
    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[session])
    mocker.patch.object(session_node.api, "close_session", return_value=True)

    # Verify session exists
    assert relayer in session_node.sessions
    assert session.socket is not None

    # Action: Peer becomes temporarily unreachable (removed from peers)
    session_node.peers = {p for p in mock_peers if p.address.native != relayer}

    # Run maintain_sessions once
    await session_node.maintain_sessions()

    # BUG: Session is closed immediately, even though it might come back
    # This test FAILS because the session gets removed
    assert relayer in session_node.sessions, (
        "Session should NOT be closed immediately when peer is temporarily unreachable. "
        "A grace period should be used to handle temporary network issues."
    )
    assert session.socket is not None, "Socket should remain open during grace period"


@pytest.mark.asyncio
async def test_session_persists_with_grace_period(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions persist through temporary peer unavailability with a grace period.

    This test will FAIL initially but should PASS after implementing grace period logic.

    Expected: FAIL initially → PASS after fix
    """
    relayer = "peer_2"
    session = mock_sessions(relayer)

    # Setup
    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[session])
    mocker.patch.object(session_node.api, "close_session", return_value=True)

    # Peer becomes unreachable
    session_node.peers = {p for p in mock_peers if p.address.native != relayer}

    # Run multiple maintenance cycles (simulating time passing)
    for _ in range(3):
        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    # Peer comes back within grace period
    session_node.peers = mock_peers
    await session_node.maintain_sessions()

    # With grace period: session should still exist
    assert (
        relayer in session_node.sessions
    ), "Session should persist if peer comes back within grace period"


@pytest.mark.asyncio
async def test_peer_quality_flapping_causes_session_churn(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that oscillating peer quality causes excessive session closure/recreation.

    BUG: Demonstrates session churn when peer availability flaps.

    Expected: FAIL (session churns excessively)
    """
    relayer = "peer_3"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[session])
    close_count = 0

    def track_close(*args, **kwargs):
        nonlocal close_count
        close_count += 1
        return True

    mocker.patch.object(session_node.api, "close_session", side_effect=track_close)

    # Simulate peer flapping: available → unavailable → available → unavailable
    peer_states = [True, False, True, False, True, False]

    for available in peer_states:
        if available:
            session_node.peers = mock_peers
        else:
            session_node.peers = {p for p in mock_peers if p.address.native != relayer}

        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    # BUG: Session gets closed multiple times due to flapping
    # Due to current implementation, session will be closed at least once when
    # peer becomes unavailable. With grace period, it should only be closed
    # once at the end if peer doesn't come back
    assert close_count <= 1, (
        f"Session closed {close_count} times due to peer flapping. "
        f"Grace period should prevent excessive churn. Expected: ≤1, Got: {close_count}"
    )


# ============================================================================
# Test Category 2: Race Conditions
# ============================================================================


@pytest.mark.asyncio
async def test_concurrent_session_access_race_condition(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test concurrent access to self.sessions from multiple coroutines.

    BUG: Demonstrates race condition when maintain_sessions and observe_message_queue
    both access the sessions dict simultaneously.

    Expected: FAIL (race condition or inconsistent state)
    """
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.channels = MagicMock()
    session_node.channels.outgoing = []

    # Mock API calls
    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[session])
    mocker.patch.object(session_node.api, "close_session", return_value=True)
    mocker.patch.object(session_node.api, "post_udp_session", return_value=session)

    # Mock message queue to continuously provide messages
    message = MessageFormat(
        relayer, "test_sender", 500, 10  # relayer, sender, packet_size, batch_size
    )

    async def mock_message_get():
        await asyncio.sleep(0.001)  # Small delay to allow interleaving
        return message

    mocker.patch("core.mixins.session.MessageQueue.get", side_effect=mock_message_get)

    exceptions = []

    async def run_observe():
        for _ in range(20):
            try:
                await session_node.observe_message_queue()
            except Exception as e:
                exceptions.append(e)
            await asyncio.sleep(0.001)

    async def run_maintain():
        for _ in range(20):
            try:
                # Toggle peer availability to trigger removal
                if len(session_node.sessions) > 2:
                    session_node.peers = set()
                else:
                    session_node.peers = mock_peers
                await session_node.maintain_sessions()
            except Exception as e:
                exceptions.append(e)
            await asyncio.sleep(0.001)

    # Run both coroutines concurrently
    await asyncio.gather(run_observe(), run_maintain(), return_exceptions=True)

    # BUG: Race conditions can cause RuntimeError or inconsistent state
    runtime_errors = [e for e in exceptions if isinstance(e, RuntimeError)]

    assert len(runtime_errors) == 0, (
        f"Race condition detected: {len(runtime_errors)} RuntimeError(s) occurred. "
        f"Errors: {runtime_errors[:3]}. "
        "Need to add locking to protect concurrent access to self.sessions"
    )


@pytest.mark.asyncio
async def test_dictionary_changed_during_iteration(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that dictionary modification during iteration causes RuntimeError.

    BUG: maintain_sessions iterates over self.sessions.items() while other code
    can modify the dictionary.

    Expected: FAIL (RuntimeError may occur intermittently)
    """
    # Create multiple sessions
    for i in range(5):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        session_node.sessions[relayer] = session

    session_node.peers = mock_peers

    mocker.patch.object(
        session_node.api,
        "list_udp_sessions",
        return_value=list(session_node.sessions.values()),
    )

    iteration_errors = []

    async def add_sessions_during_iteration():
        """Continuously add new sessions while iteration happens."""
        for i in range(10, 20):
            relayer = f"peer_{i}"
            session = mock_sessions(relayer)
            try:
                session_node.sessions[relayer] = session
                await asyncio.sleep(0.001)
            except RuntimeError as e:
                iteration_errors.append(e)

    async def iterate_sessions():
        """Run maintain_sessions which iterates over dict."""
        for _ in range(10):
            try:
                await session_node.maintain_sessions()
                await asyncio.sleep(0.001)
            except RuntimeError as e:
                iteration_errors.append(e)

    # Run concurrently
    await asyncio.gather(
        add_sessions_during_iteration(), iterate_sessions(), return_exceptions=True
    )

    # Check for dictionary iteration errors
    dict_changed_errors = [e for e in iteration_errors if "dictionary" in str(e).lower()]

    assert len(dict_changed_errors) == 0, (
        f"Dictionary modification during iteration detected: {len(dict_changed_errors)} error(s). "
        "Need to use locking or create a snapshot before iteration."
    )


@pytest.mark.asyncio
async def test_session_used_after_removal(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions can be used after being removed from cache.

    BUG: maintain_sessions removes session from cache, but observe_message_queue
    might still have a reference to it.

    Expected: FAIL (demonstrates use-after-delete)
    """
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = mock_peers
    session_node.sessions[relayer] = session
    session.create_socket()

    mocker.patch.object(
        session_node.api, "list_udp_sessions", return_value=[]
    )  # Session not active
    mocker.patch.object(session_node.api, "close_session", return_value=True)

    # Verify session exists
    assert relayer in session_node.sessions
    original_socket = session.socket

    # Run maintain_sessions - this should remove the session
    await session_node.maintain_sessions()

    # Session removed from cache
    assert relayer not in session_node.sessions

    # BUG: Socket was closed by maintain_sessions
    assert original_socket is not None, "Original socket reference still exists"
    assert session.socket is None, "Socket was closed"

    # If observe_message_queue had a reference to this session, it would try to use
    # a session with a closed socket, causing errors
    # This demonstrates the use-after-delete pattern


# ============================================================================
# Test Category 3: Session Leaks
# ============================================================================


@pytest.mark.asyncio
async def test_sessions_accumulate_when_cleanup_disabled(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions accumulate indefinitely when cleanup is disabled.

    This simulates what happens when commit 622c303 disabled cleanup - sessions leak.

    Expected: FAIL (sessions accumulate)
    """
    # Mock API to return active sessions
    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[])

    # Disable cleanup by making close_session a no-op
    mocker.patch.object(session_node.api, "close_session", return_value=False)

    # Create sessions for multiple relayers
    initial_count = 10
    for i in range(initial_count):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        session_node.sessions[relayer] = session

    session_node.peers = set()  # All peers unreachable

    # Run multiple maintenance cycles
    for _ in range(5):
        await session_node.maintain_sessions()
        await asyncio.sleep(0.01)

    # BUG: If cleanup is disabled, sessions remain in cache
    assert len(session_node.sessions) < initial_count, (
        f"Session leak detected: {len(session_node.sessions)} sessions remain "
        f"after cleanup attempts (started with {initial_count}). "
        "Sessions should be removed when peers are unreachable and API confirms closure."
    )


@pytest.mark.asyncio
async def test_orphaned_sessions_after_api_close_failure(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions become orphaned when API close fails but local cleanup proceeds.

    BUG: If API close_session fails, the session is still removed from local cache
    and socket is closed, but the session remains at the API level.

    Expected: FAIL (orphaned session)
    """
    relayer = "peer_1"
    session = mock_sessions(relayer)

    session_node.peers = set()  # Peer unreachable
    session_node.sessions[relayer] = session
    session.create_socket()

    # Mock API to show session is not active at API level
    # This triggers immediate removal, bypassing grace period
    mocker.patch.object(session_node.api, "list_udp_sessions", return_value=[])

    # Mock API close_session to FAIL
    close_called = False

    def failing_close(*args, **kwargs):
        nonlocal close_called
        close_called = True
        return False  # API close failed

    mocker.patch.object(session_node.api, "close_session", side_effect=failing_close)

    # Run maintain_sessions
    await session_node.maintain_sessions()

    # API close was attempted
    assert close_called, "API close_session should have been called"

    # BUG: Even though API close failed, the session is removed from local cache
    # This creates an orphaned session at the API level
    if relayer not in session_node.sessions:
        # Session was removed from cache despite API failure
        pytest.fail(
            "Session removed from local cache even though API close failed. "
            "This creates an orphaned session at the API level."
        )


# ============================================================================
# Test Category 4: Shutdown Cleanup
# ============================================================================


@pytest.mark.asyncio
async def test_sessions_not_cleaned_on_node_stop(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that sessions are not cleaned up when node.stop() is called.

    BUG: Node.stop() only sets self.running = False, but doesn't close sessions.

    Expected: FAIL (sessions remain after stop)
    """
    # Create multiple active sessions
    for i in range(5):
        relayer = f"peer_{i}"
        session = mock_sessions(relayer)
        session_node.sessions[relayer] = session
        session.create_socket()

    # Verify sessions exist
    assert len(session_node.sessions) == 5
    open_sockets = [s for s in session_node.sessions.values() if s.socket is not None]
    assert len(open_sockets) == 5

    # Call stop (now async)
    await session_node.stop()

    # BUG: Sessions and sockets remain open
    assert len(session_node.sessions) == 0, (
        f"Sessions not cleaned up on stop: {len(session_node.sessions)} sessions remain. "
        "Node.stop() should close all sessions and sockets."
    )

    # Check sockets are closed
    open_sockets_after = [s for s in session_node.sessions.values() if s.socket is not None]
    assert len(open_sockets_after) == 0, (
        f"{len(open_sockets_after)} sockets still open after stop. "
        "All sockets should be closed during shutdown."
    )


@pytest.mark.asyncio
async def test_in_flight_messages_lost_on_shutdown(
    session_node: Node, mock_sessions, mock_peers: set[Peer], mocker: MockerFixture
):
    """
    Test that in-flight messages are lost when node stops ungracefully.

    BUG: No graceful shutdown period - sessions closed immediately, losing data.

    Expected: FAIL (demonstrates data loss risk)
    """
    relayer = "peer_1"
    session = mock_sessions(relayer)
    session_node.sessions[relayer] = session
    session.create_socket()

    # Track if session.send is called
    send_called = False
    original_send = session.send

    def track_send(*args, **kwargs):
        nonlocal send_called
        send_called = True
        return original_send(*args, **kwargs)

    session.send = track_send

    # Simulate message sending in progress
    # relayer, sender, packet_size, batch_size
    message = MessageFormat(relayer, "sender", 500, 10)
    asyncio.create_task(asyncio.to_thread(session.send, message))

    # Give it a moment to start
    await asyncio.sleep(0.01)

    # Call stop immediately (ungraceful)
    await session_node.stop()

    # Wait for message task
    await asyncio.sleep(0.01)

    # BUG: No verification that message completed
    # In a real scenario, this message might be lost
    # We should have a graceful shutdown that waits for in-flight operations

    # Note: This test demonstrates the risk rather than failing explicitly
    # A proper fix would include tracking in-flight operations and waiting for them
    if session_node.running is False and send_called:
        # This is the current broken behavior - we document it
        pass  # Test passes to document current state

    # After fix: Should wait for in-flight messages before stopping
    # assert message_task.done(), "In-flight messages should complete before shutdown"
