from enum import Enum

from . import providers


class Type(Enum):
    SAFES = "safes_balance"
    REWARDS = "rewards"

    @property
    def provider(self) -> providers.GraphQLProvider:
        return {
            Type.SAFES: providers.Safes,
            Type.REWARDS: providers.Rewards,
        }[self]
