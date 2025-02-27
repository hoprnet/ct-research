from enum import Enum

from . import providers


class Type(Enum):
    SAFES = "safes_balance"
    STAKING = "staking"
    REWARDS = "rewards"
    MAINNET_ALLOCATIONS = "mainnet_allocations"
    GNOSIS_ALLOCATIONS = "gnosis_allocations"
    MAINNET_BALANCES = "hopr_on_mainnet"
    GNOSIS_BALANCES = "hopr_on_gnosis"
    FUNDINGS = "fundings"

    @property
    def provider(self) -> providers.GraphQLProvider:
        return {
            Type.SAFES: providers.Safes,
            Type.STAKING: providers.Staking,
            Type.REWARDS: providers.Rewards,
            Type.MAINNET_ALLOCATIONS: providers.Allocations,
            Type.GNOSIS_ALLOCATIONS: providers.Allocations,
            Type.MAINNET_BALANCES: providers.EOABalance,
            Type.GNOSIS_BALANCES: providers.EOABalance,
            Type.FUNDINGS: providers.Fundings,
        }[self]
