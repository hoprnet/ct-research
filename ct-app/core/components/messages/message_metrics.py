"""
Prometheus metrics for message processing performance.

These metrics track message throughput, worker activity, and processing latency
for the parallel message processing system.

METRICS
=======

Worker Pool Metrics:
--------------------
- MESSAGES_PROCESSED: Total messages across all workers
- WORKER_MESSAGES: Per-worker message count (labeled by worker_id)
- ACTIVE_WORKERS: Current number of running workers

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

# End-to-end delivery metrics
MESSAGES_SCHEDULED = Counter(
    "ct_messages_scheduled_total",
    "Total messages scheduled for sending (enqueued to AsyncLoop)",
)

MESSAGES_SENT_SUCCESS = Counter(
    "ct_messages_sent_success_total",
    "Total messages successfully sent (batch send completed)",
)

MESSAGES_SENT_FAILED = Counter(
    "ct_messages_sent_failed_total",
    "Total messages that failed to send",
    ["reason"],  # reasons: timeout, socket_error, session_closed, unknown
)

MESSAGE_E2E_LATENCY = Histogram(
    "ct_message_e2e_latency_seconds",
    "End-to-end message latency from queue entry to send completion",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)


def record_message_latency(phase: str, duration_seconds: float):
    """
    Record message processing latency for a specific phase.

    Args:
        phase: Processing phase (queue_wait, session, send, total)
        duration_seconds: Duration in seconds
    """
    MESSAGE_LATENCY.labels(phase=phase).observe(duration_seconds)
