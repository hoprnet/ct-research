from .base_classes import ExplicitParams
from .channel import ChannelParams
from .economic_model import EconomicModelParams
from .flags import FlagParams
from .funding import FundingParams
from .peer import PeerParams
from .sessions import SessionsParams
from .subgraph import SubgraphParams


class Parameters(ExplicitParams):
    keys: dict[str, type] = {
        "environment": str,
        "flags": FlagParams,
        "economic_model": EconomicModelParams,
        "peer": PeerParams,
        "sessions": SessionsParams,
        "channel": ChannelParams,
        "fundings": FundingParams,
        "subgraph": SubgraphParams,
    }
