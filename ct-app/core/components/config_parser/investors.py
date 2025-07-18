from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class InvestorsParams(ExplicitParams):
    addresses: list[str]
    schedule: str
