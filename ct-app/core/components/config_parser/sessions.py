from dataclasses import dataclass

from .base_classes import Duration, ExplicitParams


@dataclass(init=False)
class SessionsParams(ExplicitParams):
    green_destinations: list
    blue_destinations: list
    session_retry_base_delay: Duration
    session_retry_max_delay: Duration
    message_worker_count: int
