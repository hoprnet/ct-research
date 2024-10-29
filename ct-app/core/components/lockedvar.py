import asyncio
from typing import Any

from .baseclass import Base


class LockedVar(Base):
    """
    A class that represents a locked variable that can be accessed and modified. Any operation on the variable is asynchroneous and locked. The type of the variable can be inferred or set manually.
    """

    def __init__(self, name: str, value: Any, infer_type: bool = True):
        """
        Create a new LockedVar with the specified name and value. If infer_type is True, the type of the value will be inferred and stored, otherwise it will be None.

        :param name: The name of the variable, for logging purposes.
        :param value: The initial value of the variable. The type of the value will be inferred if infer_type is True.
        :param infer_type: Whether to infer the type of the initial value or not.
        """
        self.name = name
        self.value = value
        self.lock = asyncio.Lock()
        self.type = type(value) if infer_type else None

    async def __aenter__(self):
        await self.lock.acquire()
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        self.lock.release()

    async def get(self) -> Any:
        """
        Asynchronously get the value of the variable in a locked manner.
        """
        async with self.lock:
            if self.type:
                return self.type(self.value)
            return self.value

    async def set(self, value: Any):
        """
        Asynchronously set the value of the variable in a locked manner. If the type of the value is different from the type of the variable, a TypeError will be raised.

        :param value: The new value of the variable.
        """
        if self.type and not isinstance(value, self.type):
            raise TypeError(
                f"Trying to set value of type {type(value)} to {self.type}, ignoring"
            )

        async with self.lock:
            self.value = value

    async def update(self, value: Any):
        """
        Asynchronously update the value of the variable with the specified value in a locked manner. If the type of the value is different from the type of the variable, a TypeError will be raised.
        This method is meant to be used with dictionaries.
        """
        if self.type and not isinstance(value, self.type):
            self.warning(
                f"Trying to change value of type {type(value)} to {self.type}, ignoring"
            )
        async with self.lock:
            try:
                self.value.update(value)
            except AttributeError as e:
                raise AttributeError("Trying to call 'update' on non-dict value") from e

    @property
    def log_prefix(self):
        return f"lockedvar({self.name})"
