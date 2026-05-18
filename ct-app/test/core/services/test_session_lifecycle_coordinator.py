from core.services.session_lifecycle_coordinator import SessionLifecycleCoordinator


def test_mark_accepts_transition_event():
    coordinator = SessionLifecycleCoordinator()
    coordinator.mark("opened")
