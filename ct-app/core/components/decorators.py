import asyncio
import functools
from typing import Optional


def connectguard(func):
    """
    Decorator to check if the node is connected before running anything
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not await self.connected.get():
            self.warning("Node not connected, skipping")
            return

        return await func(self, *args, **kwargs)

    return wrapper


def flagguard(func):
    """
    Decorator to check if the feature is enabled before running it
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        cls_name = self.class_prefix()
        func_name = func.__name__

        flag = getattr(getattr(self.params.flags, cls_name), func_name, None)
        if flag is None:
            self.error(f"Feature `{func_name}` not yet available")
            return

        return await func(self, *args, **kwargs)

    return wrapper


def formalin(message: Optional[str] = None):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # _delay = Flags.getEnvironmentFlagValue(func.__name__, self.class_prefix())

            cls_name = self.class_prefix()
            func_name = func.__name__
            _delay = getattr(getattr(self.params.flags, cls_name), func_name)

            self.debug(f"Running `{func.__name__}` every {_delay} seconds")

            while self.started:
                if message:
                    self.feature(message)
                await func(self, *args, **kwargs)

                if _delay is not None:
                    await asyncio.sleep(_delay)

        return wrapper

    return decorator
