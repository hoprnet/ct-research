from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SessionsParams(ExplicitParams):
    green_destinations: list
    blue_destinations: list
    session_retry_base_delay_seconds: float
    session_retry_max_delay_seconds: float
    message_worker_count: int
