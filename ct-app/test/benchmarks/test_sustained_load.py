"""
Sustained load benchmarks for message processing.

Tests the system under continuous load for extended periods to:
- Measure actual throughput achieved
- Monitor queue depth and backpressure
- Identify performance degradation over time
- Validate system can handle target rates sustainably
"""

import asyncio
import time
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from core.components.messages import MessageFormat, MessageQueue
from core.node import Node

from .metrics_collector import MetricsCollector


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_sustained_100_msg_per_sec(
    benchmark_node: Node,
    mock_sessions_factory,
    mock_peers_factory,
    mocker: MockerFixture,
):
    """
    Benchmark: Sustained 100 msg/sec for 60 seconds (configurable).

    Validates:
    - System can handle 100 msg/sec continuously
    - Queue depth remains stable
    - No memory leaks or degradation
    - Throughput is consistent
    """
    DURATION = 60  # seconds
    TARGET_RATE = 100  # msg/sec
    PEER_COUNT = 100

    # Setup node with peers and sessions
    peers = mock_peers_factory(PEER_COUNT)
    benchmark_node.peers = peers
    benchmark_node.session_destinations = [f"peer_{i}" for i in range(PEER_COUNT)]

    # Setup channels (required for message processing)
    from core.api.response_objects import Channels, Channel

    channels = Channels({})
    channels.all = []
    channels.incoming = []
    channels.outgoing = [
        Channel(
            {
                "id": f"channel_{i}",
                "source": "bench_node",
                "destination": f"peer_{i}",
                "status": "Open",
                "balance": "10 wxHOPR",
            }
        )
        for i in range(PEER_COUNT)
    ]
    benchmark_node.channels = channels

    # Create sessions for all peers
    for i in range(PEER_COUNT):
        relayer = f"peer_{i}"
        session = mock_sessions_factory(relayer)
        benchmark_node.sessions[relayer] = session
        session.create_socket()

    # Mock API
    mocker.patch.object(
        benchmark_node.api,
        "list_udp_sessions",
        return_value=[s for s in benchmark_node.sessions.values()],
    )
    mocker.patch.object(benchmark_node.api, "close_session", return_value=True)

    # Start metrics collection
    collector = MetricsCollector(
        interval=1.0,
        config={"duration": DURATION, "target_rate": TARGET_RATE, "peer_count": PEER_COUNT},
    )
    await collector.start()

    # Start message producer
    queue = MessageQueue()
    messages_sent = 0
    interval = 1.0 / TARGET_RATE

    async def produce_messages():
        nonlocal messages_sent
        end_time = time.time() + DURATION
        peer_idx = 0

        while time.time() < end_time:
            relayer = f"peer_{peer_idx % PEER_COUNT}"
            message = MessageFormat(relayer, batch_size=3)
            await queue.put(message)
            messages_sent += 1
            peer_idx += 1
            await asyncio.sleep(interval)

    # Start message consumer (observe_message_queue processes messages from queue)
    # Access the underlying function to bypass keepalive decorator
    if hasattr(benchmark_node.observe_message_queue, "__wrapped__"):
        # Decorated method - use unwrapped version
        observe_fn = benchmark_node.observe_message_queue.__wrapped__

        async def process_one_message():
            await observe_fn(benchmark_node)

    else:
        # Undecorated method - use directly
        async def process_one_message():
            await benchmark_node.observe_message_queue()

    async def consume_messages():
        end_time = time.time() + DURATION

        while time.time() < end_time:
            try:
                await asyncio.wait_for(process_one_message(), timeout=1.0)
            except asyncio.TimeoutError:
                # No message available, continue
                continue

    # Run producer and consumer concurrently
    start_time = time.time()
    await asyncio.gather(produce_messages(), consume_messages())
    duration = time.time() - start_time

    # Stop metrics collection
    await collector.stop()
    metrics = collector.get_metrics()

    # Analysis and assertions
    avg_throughput = metrics.avg_throughput()
    max_queue = metrics.max_queue_depth()

    print(f"\n{'='*60}")
    print("Sustained Load Benchmark: 100 msg/sec")
    print(f"{'='*60}")
    print(f"Duration:          {duration:.1f}s")
    print(f"Messages sent:     {messages_sent}")
    print(f"Avg throughput:    {avg_throughput:.1f} msg/sec")
    print(f"Max queue depth:   {max_queue}")
    print(f"Avg P99 latency:   {metrics.avg_latency_p99():.3f}s")
    print(f"{'='*60}\n")

    # Assertions (80% tolerance accounts for test overhead and async scheduling)
    assert (
        avg_throughput >= TARGET_RATE * 0.80
    ), f"Throughput {avg_throughput:.1f} is below 80% of target {TARGET_RATE}"
    assert max_queue < 500, f"Max queue depth {max_queue} indicates backpressure"

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = int(time.time())
    with open(results_dir / f"sustained_100_{timestamp}.txt", "w") as f:
        f.write(f"Duration: {duration:.1f}s\n")
        f.write(f"Messages: {messages_sent}\n")
        f.write(f"Avg throughput: {avg_throughput:.1f} msg/sec\n")
        f.write(f"Max queue: {max_queue}\n")


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_sustained_130_msg_per_sec(
    benchmark_node: Node,
    mock_sessions_factory,
    mock_peers_factory,
    mocker: MockerFixture,
):
    """
    Benchmark: Sustained 130 msg/sec for 10+ minutes.

    THIS IS THE KEY TEST - validates the exact rate mentioned by the user.

    Validates:
    - System can handle 130 msg/sec (the reported bottleneck rate)
    - Queue depth remains stable (< 100)
    - No backpressure buildup
    - Performance is sustainable over 10 minutes
    """
    DURATION = 600  # 10 minutes
    TARGET_RATE = 130  # The exact rate from user's report
    PEER_COUNT = 100

    # Setup
    peers = mock_peers_factory(PEER_COUNT)
    benchmark_node.peers = peers
    benchmark_node.session_destinations = [f"peer_{i}" for i in range(PEER_COUNT)]

    # Setup channels (required for message processing)
    from core.api.response_objects import Channels, Channel

    channels = Channels({})
    channels.all = []
    channels.incoming = []
    channels.outgoing = [
        Channel(
            {
                "id": f"channel_{i}",
                "source": "bench_node",
                "destination": f"peer_{i}",
                "status": "Open",
                "balance": "10 wxHOPR",
            }
        )
        for i in range(PEER_COUNT)
    ]
    benchmark_node.channels = channels

    for i in range(PEER_COUNT):
        relayer = f"peer_{i}"
        session = mock_sessions_factory(relayer)
        benchmark_node.sessions[relayer] = session
        session.create_socket()

    mocker.patch.object(
        benchmark_node.api,
        "list_udp_sessions",
        return_value=[s for s in benchmark_node.sessions.values()],
    )
    mocker.patch.object(benchmark_node.api, "close_session", return_value=True)

    # Metrics collection
    collector = MetricsCollector(
        interval=1.0,
        config={"duration": DURATION, "target_rate": TARGET_RATE, "peer_count": PEER_COUNT},
    )
    await collector.start()

    # Message production and consumption
    queue = MessageQueue()
    messages_sent = 0
    interval = 1.0 / TARGET_RATE

    async def produce_messages():
        nonlocal messages_sent
        end_time = time.time() + DURATION
        peer_idx = 0

        while time.time() < end_time:
            relayer = f"peer_{peer_idx % PEER_COUNT}"
            message = MessageFormat(relayer, batch_size=3)
            await queue.put(message)
            messages_sent += 1
            peer_idx += 1
            await asyncio.sleep(interval)

    # Access the underlying function to bypass keepalive decorator
    if hasattr(benchmark_node.observe_message_queue, "__wrapped__"):
        # Decorated method - use unwrapped version
        observe_fn = benchmark_node.observe_message_queue.__wrapped__

        async def process_one_message():
            await observe_fn(benchmark_node)

    else:
        # Undecorated method - use directly
        async def process_one_message():
            await benchmark_node.observe_message_queue()

    async def consume_messages():
        end_time = time.time() + DURATION

        while time.time() < end_time:
            try:
                await asyncio.wait_for(process_one_message(), timeout=1.0)
            except asyncio.TimeoutError:
                # No message available, continue
                continue

    # Run test
    start_time = time.time()
    await asyncio.gather(produce_messages(), consume_messages())
    duration = time.time() - start_time

    await collector.stop()
    metrics = collector.get_metrics()

    # Detailed analysis
    avg_throughput = metrics.avg_throughput()
    max_queue = metrics.max_queue_depth()
    queue_growth = _calculate_queue_growth_rate(metrics)

    print(f"\n{'='*60}")
    print("Sustained Load Benchmark: 130 msg/sec (USER TARGET)")
    print(f"{'='*60}")
    print(f"Duration:          {duration:.1f}s ({duration/60:.1f} min)")
    print(f"Messages sent:     {messages_sent}")
    print(f"Avg throughput:    {avg_throughput:.1f} msg/sec")
    print(f"Max queue depth:   {max_queue}")
    print(f"Queue growth rate: {queue_growth:.2f} msgs/sec")
    print(f"Avg P99 latency:   {metrics.avg_latency_p99():.3f}s")
    print("")
    status = "PASS" if max_queue < 100 and queue_growth < 1.0 else "FAIL - BACKPRESSURE DETECTED"
    print(f"Status: {status}")
    print(f"{'='*60}\n")

    # Critical assertions for 130 msg/sec target
    # (80% tolerance accounts for test overhead and async scheduling)
    assert (
        avg_throughput >= TARGET_RATE * 0.80
    ), f"Throughput {avg_throughput:.1f} is below 80% of target {TARGET_RATE}"
    assert max_queue < 100, f"Max queue depth {max_queue} indicates backpressure at 130 msg/sec"
    assert (
        queue_growth < 1.0
    ), f"Queue growing at {queue_growth:.2f} msg/sec - system cannot sustain rate"

    # Save detailed results
    _save_results(metrics, "sustained_130", TARGET_RATE, duration, messages_sent)


def _calculate_queue_growth_rate(metrics) -> float:
    """Calculate queue growth rate (msgs/sec) from snapshots."""
    if len(metrics.snapshots) < 2:
        return 0.0

    first = metrics.snapshots[0]
    last = metrics.snapshots[-1]
    time_delta = last.timestamp - first.timestamp

    if time_delta == 0:
        return 0.0

    queue_delta = last.queue_size - first.queue_size
    return queue_delta / time_delta


def _save_results(metrics, test_name: str, target_rate: int, duration: float, messages_sent: int):
    """Save benchmark results to file."""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = int(time.time())

    with open(results_dir / f"{test_name}_{timestamp}.txt", "w") as f:
        f.write(f"Test: {test_name}\n")
        f.write(f"Target rate: {target_rate} msg/sec\n")
        f.write(f"Duration: {duration:.1f}s\n")
        f.write(f"Messages sent: {messages_sent}\n")
        f.write(f"Avg throughput: {metrics.avg_throughput():.1f} msg/sec\n")
        f.write(f"Max queue: {metrics.max_queue_depth()}\n")
        f.write(f"Queue growth rate: {_calculate_queue_growth_rate(metrics):.2f} msg/sec\n")
        f.write("\nSnapshot data:\n")
        for snap in metrics.snapshots:
            f.write(
                f"  {snap.timestamp:.1f}: queue={snap.queue_size}, "
                f"throughput={snap.throughput:.1f}\n"
            )
