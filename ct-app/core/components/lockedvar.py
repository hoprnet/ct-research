import asyncio
import logging
from typing import Any

from core.components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class LockedVar:
    """
    A class that represents a locked variable that can be accessed and modified.
    Any operation on the variable is asynchroneous and locked.
    The type of the variable can be inferred or set manually.
    """

    def __init__(self, name: str, value: Any, infer_type: bool = True):
        """
        Initializes a LockedVar instance with a name, initial value, and optional type enforcement.
        
        If infer_type is True, the type of the initial value is stored for future type checks.
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
        Sets the variable's value asynchronously with type enforcement.
        
        Raises:
            TypeError: If the new value's type does not match the stored type.
        """
        if self.type and not isinstance(value, self.type):
            raise TypeError(f"Trying to set value of type {type(value)} to {self.type}, ignoring")

        async with self.lock:
            self.value = value

    async def update(self, value: Any):
        """
        Asynchronously updates the current value using the provided value's data.
        
        If the stored value supports the `update()` method (such as a dictionary), merges in the contents of `value` while holding the lock. Logs a warning if the type of `value` differs from the stored type. Raises an AttributeError if the current value does not support `update()`.
        
        Args:
            value: Data to update the current value with.
        
        Raises:
            AttributeError: If the current value does not support the `update()` method.
        """
        if self.type and not isinstance(value, self.type):
            logger.warning(f"Trying to change value of type {type(value)} to {self.type}, ignoring")
        async with self.lock:
            try:
                self.value.update(value)
            except AttributeError as err:
                raise AttributeError("Trying to call 'update' on non-dict value") from err
