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


def flagguard(func):
    """
    Decorator to check if the feature is enabled before running it
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        flags = Flags.get_environment_flags("CT_FLAG_")

        if func.__name__ not in flags:
            self._info(f"Feature `{func.__name__}` not yet available")
            return

        self._debug(f"Running `{func.__name__}`")
        await func(self, *args, **kwargs)

    return wrapper
