from prometheus_client import Counter

SESSION_TRANSITIONS = Counter(
    "ct_session_lifecycle_transitions_total",
    "Session lifecycle transitions",
    ["event"],
)


class SessionLifecycleCoordinator:
    def mark(self, event: str) -> None:
        SESSION_TRANSITIONS.labels(event=event).inc()
