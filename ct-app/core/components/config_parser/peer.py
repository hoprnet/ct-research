from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class PeerParams(ExplicitParams):
    min_version: str
    sleep_mean_time: int
    sleep_std_time: int
