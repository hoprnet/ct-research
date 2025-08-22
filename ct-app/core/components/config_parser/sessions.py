from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SessionsParams(ExplicitParams):
    possible_green_destinations: list
    possible_blue_destinations: list
