import asyncio
import datetime
import functools
import logging
import os

from .utils import read_json_file
from assets.parameters_schema import schema as schema_name

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
            log.exception("Next sleep is 0 seconds..")
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


def econ_handler_wakeupcall(message: str = None):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration. The delay is specified in seconds.
    :param seconds: next whole seconds to trigger the function
    """

    def determine_delay_from_parameters():
        """
        Determines the number of seconds from the JSON contents.
        :param contents: The JSON contents returned by read_json_file function.
        :returns: (int): The number of seconds.
        """
        file_name = "parameters.json"

        script_directory = os.path.dirname(os.path.abspath(__file__))
        assets_directory = os.path.join(script_directory, "../assets")
        parameters_file_path = os.path.join(assets_directory, file_name)

        contents = read_json_file(parameters_file_path, schema_name)
        len_budget_period_sec = contents["budget_param"]["budget_period"]["value"]
        dist_number_budget_period = contents["budget_param"]["dist_freq"]["value"]
        second_delay = len_budget_period_sec / dist_number_budget_period

        return second_delay

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if message is not None:
                log.info(message)

            while self.started:
                await func(self, *args, **kwargs)

                sleep = determine_delay_from_parameters()
                log.info(f"sleep for {sleep} seconds")
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
