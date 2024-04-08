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
        func_name_clean = func.__name__.replace("_", "").lower()
        class_flags = getattr(self.params.flags, self.class_prefix())

        params_raw = dir(class_flags)
        params_clean = list(map(lambda s: s.lower(), params_raw))

        if func_name_clean not in params_clean:
            self.error(f"Feature `{func.__name__}` not in config file")
            return

        index = params_clean.index(func_name_clean)
        if getattr(class_flags, params_raw[index]) is None:
            self.error(f"Feature `{params_raw[index]}` not yet available")
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
            func_name_clean = func.__name__.replace("_", "").lower()
            class_flags = getattr(self.params.flags, self.class_prefix())

            params_raw = dir(class_flags)
            params_clean = list(map(lambda s: s.lower(), params_raw))

            if func_name_clean not in params_clean:
                self.error(f"Feature `{func.__name__}` not regonized")
                return
            
            index = params_clean.index(func_name_clean)
            delay = getattr(class_flags, params_raw[index])

            self.debug(f"Running `{params_raw[index]}` every {delay} seconds")

            while self.started:
                if message:
                    self.feature(message)
                await func(self, *args, **kwargs)

                if delay is not None:
                    await asyncio.sleep(delay)

        return wrapper

    return decorator
