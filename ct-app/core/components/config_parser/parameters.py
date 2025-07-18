from dataclasses import dataclass

from .base_classes import ExplicitParams
from .channel import ChannelParams
from .economic_model import EconomicModelParams
from .flags import FlagParams
from .investors import InvestorsParams
from .nft_holders import NFTHoldersParams
from .peer import PeerParams
from .sessions import SessionsParams
from .subgraph import SubgraphParams


@dataclass(init=False)
class Parameters(ExplicitParams):
    environment: str
    flags: FlagParams
    economic_model: EconomicModelParams
    peer: PeerParams
    sessions: SessionsParams
    channel: ChannelParams
    investors: InvestorsParams
    nft_holders: NFTHoldersParams
    subgraph: SubgraphParams
