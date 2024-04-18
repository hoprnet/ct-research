import asyncio
import logging
import pprint
import time
from datetime import timedelta
from logging import getLogger

from core.components.utils import Utils

from .metric import Metric

log = getLogger()


class EnduranceTest(object):
    def __init__(self, duration: int, rate: float):
        """
        Initialisation of the class.
        """
        self.duration = duration
        self.rate = rate
        self.iterations = int(self.duration * self.rate)

        self.tasks = set[asyncio.Task]()

        self.results = None
        self.execution_time = None
        self.metric_list: list[Metric] = []
        self._progress_bar_length = 45
        self.start_time = 0
        self.end_time = 0

        log.setLevel(getattr(logging, Utils.envvar("LOG_LEVEL", default="INFO")))
        log.disabled = not Utils.envvar("LOG_ENABLED", type=bool, default=True)

    async def progress_bar(self):
        """
        Continuously check the state of tasks in self.tasks, and print the number of
        completed tasks.
        """

        while True:
            await asyncio.sleep(0.05)

            completed_tasks = sum(task.done() for task in self.tasks)

            hash_count = int(
                completed_tasks / (len(self.tasks) - 1) * self._progress_bar_length
            )
            dash_count = self._progress_bar_length - hash_count
            duration = time.time() - self.start_time

            # format duration to mm:ss using time library
            duration_f = timedelta(seconds=int(duration))
            exp_duration_f = timedelta(seconds=int(self.duration))

            str_to_print = (
                f"\r|{'#'*hash_count}{' '*dash_count}| "
                + f"{completed_tasks}/{len(self.tasks)-1} "
                + f"[{duration_f}/{exp_duration_f}]"
            )
            print(str_to_print, end="")

            if completed_tasks == len(self.tasks) - 1:
                break

        print("\r" + " " * len(str_to_print), end="\r")

        plural = "s" if completed_tasks > 1 else ""
        self.info(f"Executed {completed_tasks} task{plural} in {duration_f}")

    async def delayed_task(self, task, iteration: int):
        await asyncio.sleep((iteration + 1) / self.rate)

        await task()

    async def _async_run(self):
        """
        Run the test.
        """

        await self.on_start()


        for it in range(self.iterations):
            self.tasks.add(
                asyncio.create_task(self.delayed_task(getattr(self, "task"), it))
            )
        self.tasks.add(asyncio.create_task(self.progress_bar()))

        Metric("Test duration", self.duration, "s").print_line()
        Metric("Test rate", self.rate, "/s").print_line()
        print("")

        self.start_time = time.time()
        await asyncio.gather(*self.tasks)
        self.end_time = time.time()

        await self.on_end()

        self.execution_time = Metric(
            "Execution time", self.end_time - self.start_time, "s"
        )

        self.metric_list = self.metrics()
        self._show_metrics()

        return self.success_flag()

    def __call__(self):
        return asyncio.run(self._async_run())

    def _show_metrics(self):
        print("")
        self.metric_list.insert(0, self.execution_time)

        for metric in self.metric_list:
            metric.print_line()

    async def on_start(self):
        raise NotImplementedError(
            "Method `on_start` not implemented. "
            + "Please create it with the following signature:\n"
            + "async def on_start(self) -> None"
        )

    async def task(self):
        raise NotImplementedError(
            "Method `task` not implemented. "
            + "Please create it with the following signature:\n"
            + "async def task(self): -> None"
        )

    async def on_end(self):
        raise NotImplementedError(
            "Method `on_end` not implemented. "
            + "Please create it with the following signature:\n"
            + "async def on_end(self) -> None"
        )

    def success_flag(self):
        self.warning(
            "Method `success_flag` not implemented. "
            + "Please create it with the following signature:\n"
            + "def success_flag(self): -> bool"
        )
        return True

    def metrics(self):
        self.warning(
            "Method `metrics` not implemented. "
            + "Please create it with the following signature:\n"
            + "def metrics(self): -> list[Metric]"
        )
        return []

    @classmethod
    def _color_print(cls, color: int, *args, **kwargs):
        prefix = kwargs.pop("prefix", "[+] ")
        no_prefix = kwargs.pop("no_prefix", False)

        if no_prefix:
            prefix = ""

        print(f"\033[{color}m{prefix}", end="")
        print(*args, **kwargs)
        print("\033[0m", end="")

    @classmethod
    def _color_pprint(cls, color: int, *args, **kwargs):
        print(f"\033[{color}m[+] ", end="")
        pprint.pprint(*args, **kwargs)
        print("\033[0m", end="")

    @classmethod
    def bold(cls, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "[•] ")
        cls._color_print(1, *args, **kwargs)

    @classmethod
    def success(cls, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "[+] ")
        cls._color_print(92, *args, **kwargs)

    @classmethod
    def info(cls, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "[-] ")
        cls._color_print(94, *args, **kwargs)

    @classmethod
    def warning(cls, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "[w] ")
        cls._color_print(93, *args, **kwargs)

    @classmethod
    def error(cls, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "[e] ")
        cls._color_print(91, *args, **kwargs)

    @classmethod
    def pprint(cls, *args, **kwargs):
        cls._color_pprint(94, *args, **kwargs)
