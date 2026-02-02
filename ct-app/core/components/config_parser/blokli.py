from dataclasses import dataclass

from .base_classes import ExplicitParams


@dataclass(init=False)
class BlokliParams(ExplicitParams):
    url: str
    token: str
