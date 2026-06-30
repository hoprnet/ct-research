"""
Ramping load benchmark to find system limits.

Gradually increases message rate to identify the breaking point where
queue depth starts growing (backpressure).
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from core.types.message_format import MessageFormat
from core.types.message_queue import MessageQueue
from core.node import Node

from .metrics_collector import MetricsCollector


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_ramping_load_find_limit(
    benchmark_node: Node,
    mock_peers_factory,
    setup_benchmark_network,
    mocker: MockerFixture,
):
    """
    Benchmark: Ramp from 50 to 250 msg/sec to find system limit.

    Starts at 50 msg/sec, increases by 10 msg/sec every 30 seconds.
    Identifies the rate where queue depth exceeds threshold (backpressure).
    """
    START_RATE = 50
    RATE_INCREMENT = 10
    STEP_DURATION = 30  # seconds per rate level
    MAX_RATE = 250
    PEER_COUNT = 100
    QUEUE_THRESHOLD = 1000  # Queue depth indicating backpressure

    # Setup
    peers = mock_peers_factory(PEER_COUNT)
    setup_benchmark_network(benchmark_node, peers)

    mocker.patch.object(
        benchmark_node.api,
        "list_udp_sessions",
        return_value=[s for s in benchmark_node.sessions.values()],
    )
    mocker.patch.object(benchmark_node.api, "close_session", return_value=True)
    mocker.patch.object(
        benchmark_node,
        "_get_or_create_session",
        new=AsyncMock(
            side_effect=lambda relayer, destination: benchmark_node.sessions.get(relayer)
        ),
    )

    collector = MetricsCollector(interval=1.0)
    await collector.start()

    # Ramping test
    current_rate = START_RATE
    breaking_point = None
    queue = MessageQueue()
    workers_task = None

    async def run_workers():
        if hasattr(benchmark_node.observe_message_queue, "__wrapped__"):
            observe_fn = benchmark_node.observe_message_queue.__wrapped__
            await observe_fn(benchmark_node)
        else:
            await benchmark_node.observe_message_queue()

    print(f"\n{'='*60}")
    print("Ramping Load Benchmark")
    print(f"{'='*60}")

    workers_task = asyncio.create_task(run_workers())

    try:
        while current_rate <= MAX_RATE:
            print(f"Testing {current_rate} msg/sec for {STEP_DURATION}s...")

            interval = 1.0 / current_rate
            end_time = time.time() + STEP_DURATION
            messages_sent = 0

            while time.time() < end_time:
                relayer = f"peer_{messages_sent % PEER_COUNT}"
                message = MessageFormat(relayer, batch_size=3)
                await queue.put(message)
                messages_sent += 1
                await asyncio.sleep(interval)

            queue_size = queue.buffer.qsize()
            print(f"  -> Queue depth: {queue_size}")

            if queue_size > QUEUE_THRESHOLD:
                breaking_point = current_rate
                print(f"  -> BACKPRESSURE DETECTED at {current_rate} msg/sec")
                break

            current_rate += RATE_INCREMENT
    finally:
        benchmark_node.running = False
        if workers_task is not None:
            try:
                await asyncio.wait_for(workers_task, timeout=5.0)
            except asyncio.TimeoutError:
                workers_task.cancel()

    await collector.stop()
    _ = collector.get_metrics()  # Collected for potential future analysis

    print("")
    print(
        f"Result: {'Breaking point found' if breaking_point else 'No breaking point within range'}"
    )
    if breaking_point:
        print(f"System limit: ~{breaking_point} msg/sec")
    print(f"{'='*60}\n")

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    with open(results_dir / f"ramping_{int(time.time())}.txt", "w") as f:
        f.write("Ramping test results\n")
        f.write(f"Breaking point: {breaking_point if breaking_point else 'Not found'} msg/sec\n")
        f.write(f"Max tested rate: {current_rate} msg/sec\n")
