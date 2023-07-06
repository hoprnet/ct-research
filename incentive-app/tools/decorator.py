import asyncio
import datetime
import functools
import logging

log = logging.getLogger(__name__)


def wakeupcall(
    message: str = None, hours: int = 0, minutes: int = 0, seconds: int = 0
):  # pragma: no cover
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration. The delay is calculated so that the function is triggered every
    whole `minutes`min and `seconds`sec.
    :param message: the message to log when the function starts
    :param minutes: next whole minute to trigger the function
    :param seconds: next whole second to trigger the function
    """

    def next_delay_in_seconds(hours: int = 0, minutes: int = 0, seconds: int = 0):
        """
        Calculates the delay until the next whole `minutes`min and `seconds`sec.
        :param minutes: next whole minute to trigger the function
        :param seconds: next whole second to trigger the function
        """

        delta = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds)

        dt = datetime.datetime.now()
        min_date = datetime.datetime.min
        try:
            next_time = min_date + round((dt - min_date) / delta + 0.5) * delta
        except ZeroDivisionError:
            log.error("Next sleep is 0 seconds..")
            return 1

        delay = int((next_time - dt).total_seconds())
        if delay == 0:
            return delta.seconds

        return delay

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if message is not None:
                log.info(message)

            sleep = next_delay_in_seconds(hours, minutes, seconds)
            await asyncio.sleep(sleep)

            while self.started:
                await func(self, *args, **kwargs)

                sleep = next_delay_in_seconds(hours, minutes, seconds)
                await asyncio.sleep(sleep)

        return wrapper

    return decorator


def formalin(message: str = None, sleep: int = None):  # pragma: no cover
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration
    :param message: the message to log when the function starts
    :param sleep: the duration to sleep after an interation
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if message is not None:
                log.info(message)

            while self.started:
                await func(self, *args, **kwargs)

                if sleep is not None:
                    await asyncio.sleep(sleep)

        return wrapper

    return decorator


def connectguard(func):  # pragma: no cover
    """
    Decorator to check if the node is connected before running anything
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.connected:
            log.warning("Node not connected, skipping")
            return

        await func(self, *args, **kwargs)

    return wrapper
