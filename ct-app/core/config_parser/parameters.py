from dataclasses import dataclass, fields

from .base_classes import ExplicitParams
from .blokli import BlokliParams
from .channel import ChannelParams
from .economic_model import EconomicModelParams
from .flags import FlagParams
from .peer import PeerParams
from .sessions import SessionsParams


@dataclass(init=False)
class Parameters(ExplicitParams):
    environment: str
    flags: FlagParams
    economic_model: EconomicModelParams
    peer: PeerParams
    channel: ChannelParams
    sessions: SessionsParams
    blokli: BlokliParams

    @staticmethod
    def _merge_dicts(base: dict, patch: dict) -> dict:
        merged = dict(base)
        for key, value in patch.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = Parameters._merge_dicts(merged[key], value)
            else:
                merged[key] = value
        return merged

    def __init__(self, data: dict | None = None):
        defaults = {
            field.name: self._default_value_for_type(field.type) for field in fields(type(self))
        }
        payload = self._merge_dicts(defaults, data or {})
        super().__init__(payload)
