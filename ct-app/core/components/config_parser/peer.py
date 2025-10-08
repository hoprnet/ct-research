from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class PeerParams(ExplicitParams):
    minimum_delay: float
    maximum_delay: float
    sleep_mean_time: float
    sleep_std_time: float
