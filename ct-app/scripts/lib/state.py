from enum import Enum
from typing import Self


class State(Enum):
    SUCCESS = "✅"
    FAILURE = "❌"
    UNKNOWN = "❓"

    @classmethod
    def fromBool(cls, value: bool) -> Self:
        return cls.SUCCESS if value else cls.FAILURE

    def __get__(self, instance, owner):
        return self.value
