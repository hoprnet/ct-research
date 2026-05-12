"""
Shared fixtures and configuration for benchmark tests.
"""

import asyncio
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest
import yaml
from pytest_mock import MockerFixture

from core.api.response_objects import Addresses, Balances, Session
from core.api.response_objects import Channel, Channels
from core.types.peer import Peer
from core.config_parser import Parameters
from core.types.message_format import MessageFormat
from core.types.message_queue import MessageQueue
from core.types.singleton import Singleton
from core.node import Node

from .metrics_collector import MetricsCollector


@pytest.fixture(autouse=True)
def clear_message_queue():
    """Clear MessageQueue singleton before each test to avoid event loop issues."""
    # Clear the singleton instance if it exists
    if MessageQueue in Singleton._instances:
        del Singleton._instances[MessageQueue]
    yield
    # Clear after test as well
    if MessageQueue in Singleton._instances:
        del Singleton._instances[MessageQueue]


@pytest.fixture
def benchmark_duration(request) -> int:
    """Get benchmark duration from CLI or use default."""
    return int(request.config.getoption("--duration", 60))


@pytest.fixture
def target_rate(request) -> int:
    """Get target message rate from CLI or use default."""
    return int(request.config.getoption("--rate", 100))


@pytest.fixture
async def benchmark_node(mocker: MockerFixture) -> Node:
    """Create a Node instance configured for benchmarking."""
    node = Node("http://localhost:3001", "benchmark_token")

    # Mock API methods
    mocker.patch.object(node.api, "address", return_value=Addresses({"native": "bench_node"}))
    mocker.patch.object(
        node.api,
        "balances",
        return_value=Balances(
            {
                "hopr": "1000 wxHOPR",
                "native": "100 xDai",
                "safeHopr": "500 wxHOPR",
                "safeNative": "50 xDai",
            }
        ),
    )
    mocker.patch.object(node.api, "healthyz", return_value=True)

    # Load test config
    cfg = Path(__file__).resolve().parents[1] / "test_config.yaml"
    with cfg.open("r") as file:
        params = Parameters(yaml.safe_load(file))

    # Configure for benchmarking
    setattr(params.flags.node, "observe_message_queue", MagicMock(value=1))
    setattr(params.flags.node, "maintain_sessions", MagicMock(value=1))

    node.params = params
    await node.retrieve_address()

    # Initialize state
    node.sessions = {}
    node.session_close_grace_period = {}
    node.session_destinations = []
    node.peers = {}

    return node


@pytest.fixture
def mock_sessions_factory():
    """Factory to create mock Session objects."""

    def _create_session(relayer: str, port: Optional[int] = None) -> Session:
        if port is None:
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
def mock_peers_factory():
    """Factory to create dictionaries of mock peers."""

    def _create_peers(count: int) -> dict[str, Peer]:
        peers = {}
        for i in range(count):
            peer = Peer(f"peer_{i}")
            peers[peer.address.native] = peer
        return peers

    return _create_peers


@pytest.fixture
def setup_benchmark_network(mock_sessions_factory):
    def _setup(node: Node, peers: dict[str, Peer]) -> None:
        node.peers = peers
        node.session_destinations = list(peers.keys())

        channels = Channels({})
        channels.all = []
        channels.incoming = []
        channels.outgoing = [
            Channel(
                {
                    "source": "bench_node",
                    "destination": address,
                    "status": "Open",
                    "balance": "10 wxHOPR",
                }
            )
            for address in peers.keys()
        ]
        node.channels = channels

        for relayer in peers.keys():
            session = mock_sessions_factory(relayer)
            node.sessions[relayer] = session
            session.create_socket()

    return _setup


@pytest.fixture
async def metrics_collector():  # type: ignore[misc]
    """Create a metrics collector for the benchmark."""
    collector = MetricsCollector(interval=1.0)
    yield collector
    # Ensure stopped
    if collector._running:
        await collector.stop()


@pytest.fixture
async def message_producer():
    """Factory to produce messages at a target rate."""

    class MessageProducer:
        def __init__(self, queue: MessageQueue):
            self.queue = queue
            self._running = False
            self._task: Optional[asyncio.Task] = None
            self._messages_sent = 0

        async def start(self, rate: int, duration: int, num_peers: int = 100):
            """
            Start producing messages.

            Args:
                rate: Target messages per second
                duration: Duration in seconds
                num_peers: Number of unique peers to cycle through
            """
            self._running = True
            self._messages_sent = 0
            self._task = asyncio.create_task(self._produce_loop(rate, duration, num_peers))

        async def stop(self):
            """Stop producing messages."""
            self._running = False
            if self._task:
                await self._task

        async def _produce_loop(self, rate: int, duration: int, num_peers: int):
            """Main message production loop."""
            interval = 1.0 / rate  # Time between messages
            end_time = asyncio.get_event_loop().time() + duration

            peer_idx = 0
            while self._running and asyncio.get_event_loop().time() < end_time:
                # Create message for a peer
                relayer = f"peer_{peer_idx % num_peers}"
                message = MessageFormat(relayer, batch_size=3)

                # Put in queue
                await self.queue.put(message)
                self._messages_sent += 1

                # Move to next peer
                peer_idx += 1

                # Wait for next message time
                await asyncio.sleep(interval)

        @property
        def messages_sent(self) -> int:
            """Total messages sent."""
            return self._messages_sent

    return MessageProducer(MessageQueue())


def pytest_addoption(parser):
    """Add benchmark-specific CLI options."""
    parser.addoption(
        "--duration",
        action="store",
        default="60",
        help="Benchmark duration in seconds (default: 60)",
    )
    parser.addoption(
        "--rate",
        action="store",
        default="100",
        help="Target message rate per second (default: 100)",
    )
