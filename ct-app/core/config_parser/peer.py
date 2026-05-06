from dataclasses import dataclass

from .base_classes import Duration, ExplicitParams


@dataclass(init=False)
class PeerParams(ExplicitParams):
    minimum_delay_between_batches: Duration
    sleep_mean_time: Duration
    sleep_std_time: Duration
    excluded_peers: list
