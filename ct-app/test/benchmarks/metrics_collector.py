"""
Metrics collection framework for benchmark runs.

Collects time-series data during benchmark execution including:
- Message throughput (msg/sec)
- Queue depth over time
- Latency percentiles
- Cache hit rates
- Resource utilization
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from prometheus_client import REGISTRY


@dataclass
class MetricsSnapshot:
    """Single point-in-time snapshot of all metrics."""

    timestamp: float
    queue_size: int
    messages_processed: int
    throughput: float  # msg/sec calculated from last snapshot
    latency_p50: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    cache_hits: Dict[str, int] = field(default_factory=dict)
    cache_misses: Dict[str, int] = field(default_factory=dict)
    session_count: int = 0


@dataclass
class BenchmarkMetrics:
    """Complete metrics collection for a benchmark run."""

    start_time: float
    end_time: Optional[float] = None
    snapshots: List[MetricsSnapshot] = field(default_factory=list)
    config: Dict = field(default_factory=dict)

    def add_snapshot(self, snapshot: MetricsSnapshot):
        """Add a metrics snapshot."""
        self.snapshots.append(snapshot)

    def duration(self) -> float:
        """Total benchmark duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

    def avg_throughput(self) -> float:
        """Average throughput across all snapshots."""
        if not self.snapshots:
            return 0.0
        return sum(s.throughput for s in self.snapshots) / len(self.snapshots)

    def max_queue_depth(self) -> int:
        """Maximum queue depth observed."""
        if not self.snapshots:
            return 0
        return max(s.queue_size for s in self.snapshots)

    def avg_latency_p99(self) -> float:
        """Average P99 latency across snapshots."""
        p99_values = [s.latency_p99 for s in self.snapshots if s.latency_p99 is not None]
        if not p99_values:
            return 0.0
        return sum(p99_values) / len(p99_values)


class MetricsCollector:
    """
    Collects metrics during benchmark execution.

    Usage:
        collector = MetricsCollector(interval=1.0)
        await collector.start()
        # ... run benchmark ...
        await collector.stop()
        metrics = collector.get_metrics()
    """

    def __init__(self, interval: float = 1.0, config: Optional[Dict] = None):
        """
        Initialize metrics collector.

        Args:
            interval: Collection interval in seconds
            config: Benchmark configuration to store with metrics
        """
        self.interval = interval
        self.metrics = BenchmarkMetrics(start_time=time.time(), config=config or {})
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_message_count = 0
        self._latency_samples: List[float] = []

    async def start(self):
        """Start collecting metrics."""
        # Initialize counter baseline from current Prometheus value
        # to avoid including messages from previous test runs
        current_count = self._get_metric("ct_messages_processed_total")
        self._last_message_count = int(current_count) if current_count else 0

        self._running = True
        self._task = asyncio.create_task(self._collection_loop())

    async def stop(self):
        """Stop collecting metrics."""
        self._running = False
        if self._task:
            await self._task
        self.metrics.end_time = time.time()

    def record_latency(self, latency_seconds: float):
        """Record a single message latency sample."""
        self._latency_samples.append(latency_seconds)

    def get_metrics(self) -> BenchmarkMetrics:
        """Get collected metrics."""
        return self.metrics

    async def _collection_loop(self):
        """Main collection loop."""
        while self._running:
            try:
                snapshot = self._collect_snapshot()
                self.metrics.add_snapshot(snapshot)
                await asyncio.sleep(self.interval)
            except Exception as e:
                print(f"Error collecting metrics: {e}")
                await asyncio.sleep(self.interval)

    def _collect_snapshot(self) -> MetricsSnapshot:
        """Collect a single metrics snapshot from Prometheus."""
        now = time.time()

        # Get metrics from Prometheus registry
        queue_size = self._get_metric("ct_queue_size")
        messages_processed = self._get_metric("ct_messages_processed_total")

        # Calculate throughput since last snapshot
        throughput = 0.0
        if messages_processed is not None:
            messages_delta = messages_processed - self._last_message_count
            throughput = messages_delta / self.interval
            self._last_message_count = int(messages_processed)

        # Calculate latency percentiles from samples
        latency_p50, latency_p95, latency_p99 = self._calculate_latency_percentiles()

        # Cache metrics
        cache_hits = self._get_cache_metrics("hits")
        cache_misses = self._get_cache_metrics("misses")

        # Session count
        session_count = self._get_metric("ct_session_count", default=0)

        return MetricsSnapshot(
            timestamp=now,
            queue_size=int(queue_size) if queue_size else 0,
            messages_processed=int(messages_processed) if messages_processed else 0,
            throughput=throughput,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            session_count=int(session_count) if session_count else 0,
        )

    def _get_metric(self, name: str, default: Optional[float] = None) -> Optional[float]:
        """Get a metric value from Prometheus registry."""
        try:
            for metric in REGISTRY.collect():
                # Check if any sample matches the requested name
                # (metric.name might be ct_messages_processed
                # while sample.name is ct_messages_processed_total)
                for sample in metric.samples:
                    if sample.name == name:
                        return sample.value
        except Exception:
            pass
        return default

    def _get_cache_metrics(self, metric_type: str) -> Dict[str, int]:
        """Get cache hit/miss metrics by cache type."""
        metrics = {}
        metric_name = f"ct_cache_{metric_type}_total"
        try:
            for metric in REGISTRY.collect():
                if metric.name == metric_name:
                    for sample in metric.samples:
                        if "cache_type" in sample.labels:
                            cache_type = sample.labels["cache_type"]
                            metrics[cache_type] = int(sample.value)
        except Exception:
            pass
        return metrics

    def _calculate_latency_percentiles(
        self,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate P50, P95, P99 from latency samples."""
        if not self._latency_samples:
            return None, None, None

        sorted_samples = sorted(self._latency_samples)
        n = len(sorted_samples)

        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        p50 = sorted_samples[p50_idx] if p50_idx < n else None
        p95 = sorted_samples[p95_idx] if p95_idx < n else None
        p99 = sorted_samples[p99_idx] if p99_idx < n else None

        # Clear samples for next interval
        self._latency_samples = []

        return p50, p95, p99
