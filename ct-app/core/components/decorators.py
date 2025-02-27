import asyncio
import functools
import logging

from core.components.logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


def master(*decorators):
    """
    Decorator to combine multiple decorators into one
    """
    def decorator(func):
        for decorator in reversed(decorators):
            func = decorator(func)
        return func
    return decorator


def connectguard(func):
    """
    Decorator to check if the node is connected before running anything
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.connected:
            logger.warning("Node not connected, skipping")
            return

        return await func(self, *args, **kwargs)

    return wrapper


def flagguard(func):
    """
    Decorator to check if the feature is enabled before running it
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        class_flags = getattr(self.params.flags, self.__class__.__name__.lower())
        flag = getattr(class_flags, func.__name__)

        if flag is None or flag is False:
            logger.debug("Feature not enabled, skipping", {"feature": func.__name__})
            return

        return await func(self, *args, **kwargs)

    return wrapper


def formalin(func):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        class_flags = getattr(self.params.flags, self.__class__.__name__.lower())
        delay = getattr(class_flags, func.__name__)

        if delay is True:
            delay = 0
        if delay is False:
            delay = None

        logger.debug("Running method continuously", {"method": func.__name__, "delay": delay})

        while self.running:
            await func(self, *args, **kwargs)

            if delay is None:
                break
            await asyncio.sleep(delay)

    return wrapper