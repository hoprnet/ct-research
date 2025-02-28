from enum import Enum

from .parameters import LegacyParams, SigmoidParams


class EconomicModelTypes(Enum):
    LEGACY = "legacy"
    SIGMOID = "sigmoid"

    @property
    def model(self):
        return {
            EconomicModelTypes.LEGACY: LegacyParams,
            EconomicModelTypes.SIGMOID: SigmoidParams,
        }[self]
