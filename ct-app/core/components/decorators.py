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
    Asynchronous decorator that checks if a feature flag is enabled before executing the method.
    
    The decorator verifies the presence and value of a feature flag corresponding to the method in the instance's configuration. If the flag is missing, disabled, or not properly configured, the method is skipped and an error is logged. If the flag is enabled, the method is executed.
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        """
        Checks if a feature flag is enabled for the method before execution.
        
        If the required flags configuration or method-specific flag is missing or disabled,
        the method is not executed and an error is logged. Otherwise, the method is awaited
        and its result is returned.
        """
        func_name_clean = func.__name__.replace("_", "").lower()

        if not hasattr(self.params, "flags"):
            logger.error("No class listed in config file as might contain long running tasks")
            return

        if not hasattr(self.params.flags, self.__class__.__name__.lower()):
            logger.error(
                "Class not listed in config file as might contain long running tasks",
                {"class": self.__class__.__name__.lower()},
            )
            return

        class_flags = getattr(self.params.flags, self.__class__.__name__.lower())

        params_raw = dir(class_flags)
        params_clean = list(map(lambda s: s.lower(), params_raw))

        if func_name_clean not in params_clean:
            logger.error(
                "Method not listed in config file as a long running task",
                {"method": func.__name__},
            )
            return

        index = params_clean.index(func_name_clean)
        feature = params_raw[index]
        flag = getattr(class_flags, feature)

        if flag is None or flag is False:
            return

        return await func(self, *args, **kwargs)

    return wrapper


def formalin(func):
    """
    Decorator that repeatedly executes an asynchronous method while the instance is running.
    
    The decorated method is invoked in a loop as long as the instance's `running` attribute is `True`. The delay between iterations is determined by a class-specific flag in `params.flags` corresponding to the method name. If the flag is `True`, the method runs continuously with no delay; if `False`, it runs only once. If the flag is a numeric value, it specifies the delay in seconds between executions. The method is skipped if it is not listed in the configuration flags.
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        """
        Continuously executes an asynchronous method while the instance is running, with optional delay.
        
        Retrieves a delay value from class-specific flags and repeatedly runs the decorated method as long as the instance's `running` attribute is `True`. If the delay is `None`, the method runs only once; if the delay is a number, it waits for that duration between executions.
        """
        func_name_clean = func.__name__.replace("_", "").lower()

        class_flags = getattr(self.params.flags, self.__class__.__name__.lower())

        params_raw = dir(class_flags)
        params_clean = list(map(lambda s: s.lower(), params_raw))

        if func_name_clean not in params_clean:
            logger.error(
                "Method not listed in config file as a long running task",
                {"method": func.__name__},
            )
            return

        index = params_clean.index(func_name_clean)
        delay = getattr(class_flags, params_raw[index])

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
