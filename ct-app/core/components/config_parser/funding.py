from dataclasses import dataclass

from core.components.balance import Balance

from .base_classes import ExplicitParams


@dataclass(init=False)
class FundingParams(ExplicitParams):
    constant: Balance
