from dataclasses import dataclass, field

from .base_classes import ExplicitParams


@dataclass(init=False, repr=False)
class BlokliParams(ExplicitParams):
    url: str = field(metadata={"env": "BLOKLI_URL"})
    token: str = field(metadata={"env": "BLOKLI_TOKEN"})
