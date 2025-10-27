"""
Prometheus metrics for message processing performance.

These metrics are used by the benchmark suite to measure throughput,
latency, and cache performance.
"""

from prometheus_client import Counter, Gauge, Histogram

# Message processing counters
MESSAGES_PROCESSED = Counter("ct_messages_processed_total", "Total messages processed")

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
