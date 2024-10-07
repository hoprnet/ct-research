from enum import Enum

from . import providers


class Type(Enum):
    SAFES = "safesBalance"
    STAKING = "staking"
    REWARDS = "rewards"
    MAINNET_ALLOCATIONS = "mainnetAllocations"
    GNOSIS_ALLOCATIONS = "gnosisAllocations"
    MAINNET_BALANCES = "hoprOnMainet"
    GNOSIS_BALANCES = "hoprOnGnosis"
    FUNDINGS = "fundings"

    @property
    def provider(self):
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
