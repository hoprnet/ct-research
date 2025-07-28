from enum import Enum
from typing import Callable

from . import providers


class Type(Enum):
    SAFES = "safes_balance"
    REWARDS = "rewards"

    @property
    def provider(self) -> Callable:
        return {
            Type.SAFES: providers.Safes,
            Type.REWARDS: providers.Rewards,
        }[self]
