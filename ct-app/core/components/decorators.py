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

        if not hasattr(self.params, "flags"):
            self.error("No flags available")
            return

        if not hasattr(self.params.flags, self.class_prefix()):
            raise AttributeError(f"Feature `{func.__name__}` not in config file")

        class_flags = getattr(self.params.flags, self.class_prefix())

        params_raw = dir(class_flags)
        params_clean = list(map(lambda s: s.lower(), params_raw))

        if func_name_clean not in params_clean:
            raise AttributeError(f"Feature `{func.__name__}` not in config file")

        index = params_clean.index(func_name_clean)
        feature = params_raw[index]
        flag = getattr(class_flags, feature)

        if flag is None or flag is False:
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

            if delay is True:
                delay = 0
            if delay is False:
                delay = None

            if delay == 0:
                self.info(f"Running `{params_raw[index]}` continuously")
            elif delay is not None:
                self.info(f"Running `{params_raw[index]}` every {delay} seconds")

            while self.running:
                if message:
                    self.feature(message)
                await func(self, *args, **kwargs)

                if delay is None:
                    break
                await asyncio.sleep(delay)

        return wrapper

    return decorator
