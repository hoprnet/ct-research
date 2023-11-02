import asyncio
import functools

from .flags import Flags


def connectguard(func):
    """
    Decorator to check if the node is connected before running anything
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not await self.connected.get():
            self._warning("Node not connected, skipping")
            return

        await func(self, *args, **kwargs)

    return wrapper


def flagguard(prefix: str):
    """
    Decorator to check if the feature is enabled before running it
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            flags = Flags.get_environment_flags(prefix)

            if func.__name__ not in flags:
                self._info(f"Feature `{func.__name__}` not yet available")
                return

            self._debug(f"Running `{func.__name__}`")
            await func(self, *args, **kwargs)

        return wrapper

    return decorator


def formalin(delay: int = None, flag_prefix: str = None):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration
    :param delay: the duration to sleep after an interation
    :param from_flag: whether to infer delay from the flag environment variable value
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            _delay = delay
            if flag_prefix:
                _delay = Flags.get_environment_flag_value(func.__name__, flag_prefix)

            self._info(f"Running `{func.__name__}` every {_delay} seconds")

            while self.started:
                await func(self, *args, **kwargs)

                if _delay is not None:
                    await asyncio.sleep(_delay)

        return wrapper

    return decorator
