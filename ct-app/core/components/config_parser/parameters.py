from dataclasses import dataclass

from .base_classes import ExplicitParams
from .channel import ChannelParams
from .economic_model import EconomicModelParams
from .flags import FlagParams
from .peer import PeerParams
from .sessions import SessionsParams
from .subgraph import SubgraphParams


@dataclass(init=False)
class Parameters(ExplicitParams):
    environment: str
    flags: FlagParams
    economic_model: EconomicModelParams
    peer: PeerParams
    channel: ChannelParams
    sessions: SessionsParams
    subgraph: SubgraphParams
