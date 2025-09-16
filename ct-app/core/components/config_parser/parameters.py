from dataclasses import dataclass

from .base_classes import ExplicitParams
from .channel import ChannelParams
from .economic_model import EconomicModelParams
from .flags import FlagParams
from .investors import InvestorsParams
from .nft_holders import NFTHoldersParams
from .peer import PeerParams
from .rpc import RPCParams
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
    investors: InvestorsParams
    nft_holders: NFTHoldersParams
    rpc: RPCParams
    subgraph: SubgraphParams
