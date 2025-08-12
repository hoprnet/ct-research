from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class RPCParams(ExplicitParams):
    gnosis: str
    mainnet: str
