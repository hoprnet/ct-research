from enum import Enum
from typing import Mapping

from api_lib.objects import JsonResponse

from . import providers
from .blokli_provider import BlokliProvider


class Type(Enum):
    SAFES = "safes_balance"
    VERSION = "version"

    @property
    def provider(self) -> type[BlokliProvider[JsonResponse]]:
        providers_by_type: Mapping["Type", type[BlokliProvider[JsonResponse]]] = {
            Type.SAFES: providers.Safes,
            Type.VERSION: providers.Version,
        }
        return providers_by_type[self]
