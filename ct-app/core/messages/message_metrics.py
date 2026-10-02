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

# End-to-end delivery metrics
MESSAGES_SCHEDULED = Counter(
    "ct_messages_scheduled_total",
    "Total messages scheduled for sending (enqueued to AsyncLoop)",
)

MESSAGE_REQUEUES = Counter(
    "ct_message_requeue_total",
    "Total messages requeued for retry",
    ["reason"],
)

MESSAGE_DROPS = Counter(
    "ct_message_drop_total",
    "Total messages dropped instead of being retried",
    ["reason"],
)

SESSION_OPEN_EVENTS = Counter(
    "ct_session_open_events_total",
    "Session open lifecycle events recorded by the message workers",
    ["result"],
)

BATCH_SCHEDULE_FAILURES = Counter(
    "ct_batch_schedule_failures_total",
    "Total batch send scheduling failures in the message workers",
)

WORKER_LOOP_EVENTS = Counter(
    "ct_worker_loop_events_total",
    "Worker loop events recorded by the message workers",
    ["event"],
)

MESSAGES_SENT_SUCCESS = Counter(
    "ct_messages_sent_success_total",
    "Total bursts successfully sent (burst send completed)",
)

MESSAGES_SENT_FAILED = Counter(
    "ct_messages_sent_failed_total",
    "Total messages that failed to send",
    ["reason"],  # reasons: timeout, socket_error, session_closed, unknown
)

MESSAGE_E2E_LATENCY = Histogram(
    "ct_message_e2e_latency_seconds",
    "End-to-end message latency from queue entry to send completion",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0),
)

# Burst incentive model
BURSTS = Counter(
    "ct_bursts_total",
    "Bursts handled by the round scheduler",
    ["result"],  # results: queued, skipped_ineligible
)
ACTIVE_BURSTS = Gauge("ct_active_bursts", "Bursts currently being sent")
BURST_PACKETS_SENT = Counter(
    "ct_burst_packets_sent_total",
    "Packets sent in bursts",
    ["relayer"],
)
BURST_PACKETS_ECHOED = Counter(
    "ct_burst_packets_echoed_total",
    "Burst packets echoed back, each relayed twice (out and back)",
    ["relayer"],
)
RELAYED_VALUE = Counter(
    "ct_relayed_value_total",
    "Expected wxHOPR paid for relayed burst packets (2 tickets per echoed packet)",
)
MONTH_TO_DATE_COST = Gauge(
    "ct_month_to_date_cost",
    "Expected wxHOPR paid for relayed burst packets since the start of the UTC month",
)
ROUND_RELAYERS = Gauge("ct_round_relayers", "Relayers in the current round")
ROUND_DURATION = Gauge("ct_round_duration_seconds", "Length of the current round")
ROUND_STEP = Gauge("ct_round_step_seconds", "Time between two burst starts in the current round")
ROUND_CONCURRENCY = Gauge(
    "ct_round_concurrency", "Average bursts running at once in the current round"
)
PROJECTED_MONTHLY_COST = Gauge(
    "ct_projected_max_monthly_cost",
    "Projected maximum monthly cost of the network at 100% relay, from the current round",
)
