from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SessionsParams(ExplicitParams):
    batch_size: int
    green_destinations: list
    blue_destinations: list
