"""
Prometheus metrics for message processing performance.

These metrics track message throughput, worker activity, cache efficiency,
and processing latency for the parallel message processing system (Phase 2).

PHASE 2 METRICS
===============

Worker Pool Metrics:
--------------------
- MESSAGES_PROCESSED: Total messages across all workers
- WORKER_MESSAGES: Per-worker message count (labeled by worker_id)
- ACTIVE_WORKERS: Current number of running workers (0 or 10)

Usage:
------
- MESSAGES_PROCESSED.inc() - Increments total counter
- WORKER_MESSAGES.labels(worker_id=0).inc() - Increments worker 0's counter
- ACTIVE_WORKERS.set(10) - Sets active workers to 10

Performance Monitoring:
-----------------------
Query WORKER_MESSAGES to identify:
- Load imbalance (some workers process more than others)
- Worker stalls (worker_id counter not incrementing)
- Throughput per worker (rate(WORKER_MESSAGES[1m]))

Aggregate throughput:
  rate(MESSAGES_PROCESSED[1m])

Per-worker throughput:
  rate(WORKER_MESSAGES{worker_id="0"}[1m])

Worker utilization:
  ACTIVE_WORKERS / 10 * 100%
"""

from prometheus_client import Counter, Gauge, Histogram

# Message processing counters
MESSAGES_PROCESSED = Counter("ct_messages_processed_total", "Total messages processed")

# Worker metrics (Phase 2 parallel processing)
WORKER_MESSAGES = Counter(
    "ct_worker_messages_total",
    "Messages processed per worker (Phase 2 parallel processing)",
    ["worker_id"],
)
ACTIVE_WORKERS = Gauge(
    "ct_active_workers",
    "Number of active message workers (0=stopped, 10=running)",
)

# Session count
SESSION_COUNT = Gauge("ct_session_count", "Number of active sessions")

# Message processing latency
MESSAGE_LATENCY = Histogram(
    "ct_message_latency_seconds",
    "Message processing latency",
    ["phase"],  # phases: queue_wait, session, send, total
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
)

# Cache performance metrics
CACHE_HITS = Counter("ct_cache_hits_total", "Cache hits", ["cache_type"])

CACHE_MISSES = Counter("ct_cache_misses_total", "Cache misses", ["cache_type"])


def record_cache_access(cache_type: str, hit: bool):
    """
    Record a cache access (hit or miss).

    Args:
        cache_type: Type of cache (peer_addresses, channels, destinations)
        hit: True if cache hit, False if cache miss
    """
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()


def record_message_latency(phase: str, duration_seconds: float):
    """
    Record message processing latency for a specific phase.

    Args:
        phase: Processing phase (queue_wait, session, send, total)
        duration_seconds: Duration in seconds
    """
    MESSAGE_LATENCY.labels(phase=phase).observe(duration_seconds)
