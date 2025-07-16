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
    safes_balance: SubgraphEndpointParams
    rewards: SubgraphEndpointParams
