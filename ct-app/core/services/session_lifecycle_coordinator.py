from prometheus_client import Counter
from ..constants.labels import SessionLifecycleEvent

SESSION_TRANSITIONS = Counter(
    "ct_session_lifecycle_transitions_total",
    "Session lifecycle transitions",
    ["event"],
)


class SessionLifecycleCoordinator:
    def mark(self, event: "SessionLifecycleEvent") -> None:
        SESSION_TRANSITIONS.labels(event=event.value).inc()
