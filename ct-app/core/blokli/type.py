from enum import Enum
from typing import Callable

from . import providers


class Type(Enum):
    SAFES = "safes_balance"
    VERSION = "version"

    @property
    def provider(self) -> Callable:
        return {
            Type.SAFES: providers.Safes,
            Type.VERSION: providers.Version,
        }[self]
