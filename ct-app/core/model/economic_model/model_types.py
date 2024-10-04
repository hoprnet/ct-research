from enum import Enum

from .economic_model_legacy import EconomicModelLegacy
from .economic_model_sigmoid import EconomicModelSigmoid


class EconomicModelTypes(Enum):
    LEGACY = "legacy"
    SIGMOID = "sigmoid"

    def __call__(self):
        return {
            EconomicModelTypes.LEGACY: EconomicModelLegacy,
            EconomicModelTypes.SIGMOID: EconomicModelSigmoid,
        }[self]
