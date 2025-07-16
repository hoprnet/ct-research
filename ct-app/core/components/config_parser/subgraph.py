from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SubgraphEndpointParams(ExplicitParams):
    query_id: str
    slug: str
    inputs: dict

    def __post_init__(self):
        if self.inputs is None:
            self.inputs = dict()


@dataclass(init=False)
class SubgraphParams(ExplicitParams):
    type: str
    user_id: int
    api_key: str
    mainnet_allocations: SubgraphEndpointParams
    gnosis_allocations: SubgraphEndpointParams
    hopr_on_mainnet: SubgraphEndpointParams
    hopr_on_gnosis: SubgraphEndpointParams
    safes_balance: SubgraphEndpointParams
    fundings: SubgraphEndpointParams
    rewards: SubgraphEndpointParams
    staking: SubgraphEndpointParams
