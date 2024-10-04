from enum import Enum

from . import graphql_providers


class SubgraphTypes(Enum):
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
            SubgraphTypes.SAFES: graphql_providers.Safes,
            SubgraphTypes.STAKING: graphql_providers.Staking,
            SubgraphTypes.REWARDS: graphql_providers.Rewards,
            SubgraphTypes.MAINNET_ALLOCATIONS: graphql_providers.Allocations,
            SubgraphTypes.GNOSIS_ALLOCATIONS: graphql_providers.Allocations,
            SubgraphTypes.MAINNET_BALANCES: graphql_providers.EOABalance,
            SubgraphTypes.GNOSIS_BALANCES: graphql_providers.EOABalance,
            SubgraphTypes.FUNDINGS: graphql_providers.Fundings,
        }[self]
