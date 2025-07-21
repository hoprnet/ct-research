from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class SubgraphEndpointParams(ExplicitParams):
    query_id: str
    slug: str


@dataclass(init=False)
class SubgraphParams(ExplicitParams):
    type: str
    user_id: int
    api_key: str

    safes_balance: SubgraphEndpointParams
    rewards: SubgraphEndpointParams
