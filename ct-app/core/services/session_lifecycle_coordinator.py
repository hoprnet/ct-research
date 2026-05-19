from enum import Enum

from prometheus_client import Counter

SESSION_TRANSITIONS = Counter(
    "ct_session_lifecycle_transitions_total",
    "Session lifecycle transitions",
    ["event"],
)


class SessionLifecycleCoordinator:
    def mark(self, event: "SessionLifecycleEvent") -> None:
        SESSION_TRANSITIONS.labels(event=event.value).inc()


class SessionLifecycleEvent(str, Enum):
    RETIRE_REQUESTED = "retire_requested"
    RETIRE_FAILED = "retire_failed"
    RETIRED = "retired"
    OPEN_REQUESTED = "open_requested"
    OPEN_RATE_LIMITED = "open_rate_limited"
    OPEN_FAILED = "open_failed"
    OPENED = "opened"
    OPEN_RACE_REUSED = "open_race_reused"
    MAINTENANCE_CLOSE_REQUESTED = "maintenance_close_requested"
    MAINTENANCE_CLOSE_FAILED = "maintenance_close_failed"
    MAINTENANCE_CLOSED = "maintenance_closed"
