from dataclasses import dataclass
from pathlib import Path

from .base_classes import ExplicitParams


@dataclass(init=False)
class NFTHoldersParams(ExplicitParams):
    filepath: Path
