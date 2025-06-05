from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SessionsParams(ExplicitParams):
    aggregated_packets: int
    batch_size: int
