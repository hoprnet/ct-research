from core.components.balance import Balance

from .base_classes import ExplicitParams


class FundingParams(ExplicitParams):
    keys = {"constant": Balance}
