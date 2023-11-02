import asyncio
from typing import Any

from .baseclass import Base


class LockedVar(Base):
    def __init__(self, name: str, value: Any, infer_type: bool = True):
        self.name = name
        self.value = value
        self.lock = asyncio.Lock()

        if infer_type:
            self.type = type(value)
        else:
            self.type = None

    async def get(self) -> Any:
        async with self.lock:
            if self.type:
                return self.type(self.value)
            return self.value

    async def set(self, value: Any):
        if self.type and not isinstance(value, self.type):
            self._warning(
                f"Trying to set value of type {type(value)} to {self.type}, ignoring"
            )

        async with self.lock:
            self.value = value

    @property
    def print_prefix(self):
        return f"LockedVar({self.name})"
