from enum import Enum

from . import providers
from .graphql_provider import GraphQLProvider


class Type(Enum):
    SAFES = "safes_balance"
    REWARDS = "rewards"

    @property
    def provider(self) -> GraphQLProvider:
        return {
            Type.SAFES: providers.Safes,
            Type.REWARDS: providers.Rewards,
        }[self]
