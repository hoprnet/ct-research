from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False, repr=False)
class PeerParams(ExplicitParams):
    excluded_peers: list
