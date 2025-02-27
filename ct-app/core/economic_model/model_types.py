from enum import Enum

from core.components.parameters import LegacyParams, SigmoidParams


class EconomicModelTypes(Enum):
    LEGACY = "legacy"
    SIGMOID = "sigmoid"

    @property
    def model(self):
        return {
            EconomicModelTypes.LEGACY: LegacyParams,
            EconomicModelTypes.SIGMOID: SigmoidParams,
        }[self]
