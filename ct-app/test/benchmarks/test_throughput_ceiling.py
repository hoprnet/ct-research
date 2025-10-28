"""
Throughput ceiling benchmark.

Tests increasing message rates with shorter durations to find the maximum
sustainable throughput before backpressure occurs.
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
async def test_throughput_ceiling(
    benchmark_node: Node,
    mock_sessions_factory,
    mock_peers_factory,
    mocker: MockerFixture,
):
    """
    Benchmark: Find maximum sustainable throughput.

    Tests rates: 130, 150, 180, 200, 250 msg/sec
    Duration: 60 seconds per rate
    Success criteria: Queue depth < 100, queue growth < 1.0 msg/sec
    """
    TEST_RATES = [130, 150, 180, 200, 250]
    DURATION = 60  # seconds per test
    PEER_COUNT = 100

    # Setup node
    peers = mock_peers_factory(PEER_COUNT)
    benchmark_node.peers = peers
    benchmark_node.session_destinations = [f"peer_{i}" for i in range(PEER_COUNT)]

    # Setup channels
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

    # Create sessions
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

    print(f"\n{'='*60}")
    print("Throughput Ceiling Benchmark")
    print(f"{'='*60}\n")

    results = {}

    for target_rate in TEST_RATES:
        print(f"Testing {target_rate} msg/sec for {DURATION}s...")

        # Start metrics collection
        collector = MetricsCollector(
            interval=1.0,
            config={"duration": DURATION, "target_rate": target_rate, "peer_count": PEER_COUNT},
        )
        await collector.start()

        # Message production and consumption
        queue = MessageQueue()
        messages_sent = 0
        interval = 1.0 / target_rate

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

        # Start workers
        async def run_workers():
            """Run the message worker pool for the test duration."""
            if hasattr(benchmark_node.observe_message_queue, "__wrapped__"):
                observe_fn = benchmark_node.observe_message_queue.__wrapped__
                await observe_fn(benchmark_node)
            else:
                await benchmark_node.observe_message_queue()

        # Run test
        start_time = time.time()
        workers_task = asyncio.create_task(run_workers())
        producer_task = asyncio.create_task(produce_messages())

        # Wait for producer to finish
        await producer_task

        # Stop workers
        benchmark_node.running = False

        # Wait for workers to stop
        try:
            await asyncio.wait_for(workers_task, timeout=5.0)
        except asyncio.TimeoutError:
            workers_task.cancel()

        duration = time.time() - start_time

        await collector.stop()
        metrics = collector.get_metrics()

        # Analysis
        avg_throughput = metrics.avg_throughput()
        max_queue = metrics.max_queue_depth()
        queue_growth = _calculate_queue_growth_rate(metrics)

        # Determine pass/fail
        passed = max_queue < 100 and queue_growth < 1.0
        status = "PASS ✓" if passed else "FAIL ✗"

        print(f"  Avg throughput: {avg_throughput:.1f} msg/sec")
        print(f"  Max queue depth: {max_queue}")
        print(f"  Queue growth rate: {queue_growth:.2f} msg/sec")
        print(f"  Status: {status}\n")

        results[target_rate] = {
            "throughput": avg_throughput,
            "max_queue": max_queue,
            "queue_growth": queue_growth,
            "passed": passed,
        }

        # Stop testing if we hit the ceiling
        if not passed:
            print(f"Throughput ceiling found at {target_rate} msg/sec")
            break

        # Reset node state for next iteration
        benchmark_node.running = True

    # Summary
    print(f"\n{'='*60}")
    print("Throughput Ceiling Results")
    print(f"{'='*60}")
    for rate, data in results.items():
        status = "PASS ✓" if data["passed"] else "FAIL ✗"
        print(f"{rate} msg/sec: {data['throughput']:.1f} actual | Queue: {data['max_queue']} | {status}")

    # Find maximum sustainable rate
    max_rate = max([rate for rate, data in results.items() if data["passed"]], default=0)
    print(f"\nMaximum sustainable throughput: {max_rate} msg/sec")
    print(f"{'='*60}\n")

    # Save results
    _save_ceiling_results(results, max_rate)

    # Assert at least 130 msg/sec is achievable (our baseline target)
    assert 130 in results and results[130]["passed"], "Failed to achieve baseline 130 msg/sec"


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


def _save_ceiling_results(results: dict, max_rate: int):
    """Save throughput ceiling results to file."""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = int(time.time())

    with open(results_dir / f"ceiling_{timestamp}.txt", "w") as f:
        f.write("Throughput Ceiling Benchmark Results\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"Maximum sustainable rate: {max_rate} msg/sec\n\n")
        f.write("Detailed results:\n")
        for rate, data in results.items():
            status = "PASS" if data["passed"] else "FAIL"
            f.write(f"{rate} msg/sec:\n")
            f.write(f"  Throughput: {data['throughput']:.1f} msg/sec\n")
            f.write(f"  Max queue: {data['max_queue']}\n")
            f.write(f"  Queue growth: {data['queue_growth']:.2f} msg/sec\n")
            f.write(f"  Status: {status}\n\n")
