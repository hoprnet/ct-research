import asyncio
import logging
import pprint
import time
from datetime import timedelta

from tools.utils import envvar, getlogger

from .metric import Metric

log = getlogger()


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

        log.setLevel(getattr(logging, envvar("LOG_LEVEL", default="INFO")))
        log.disabled = not envvar("LOG_ENABLED", type=bool, default=True)

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

            print(
                f"\r|{'#'*hash_count}{' '*dash_count}| "
                + f"{completed_tasks}/{len(self.tasks)-1} "
                + f"[{duration_f}/{exp_duration_f}]",
                end="",
            )

            if completed_tasks == len(self.tasks) - 1:
                break
        print("")

    async def delayed_task(self, task, iteration: int):
        await asyncio.sleep((iteration + 1) / self.rate)

        await task()

    async def _async_run(self):
        """
        Run the test.
        """

        for it in range(self.iterations):
            self.tasks.add(
                asyncio.create_task(self.delayed_task(getattr(self, "task"), it))
            )
        self.tasks.add(asyncio.create_task(self.progress_bar()))

        Metric("Test duration", self.duration, "s").print_line()
        Metric("Test rate", self.rate, "/s").print_line()
        print("")

        await self.on_start()

        self.start_time = time.time()
        await asyncio.gather(*self.tasks)
        self.end_time = time.time()

        await self.on_end()

        self.execution_time = Metric(
            "Execution time", self.end_time - self.start_time, "s"
        )

        self.metric_list = self.metrics()
        self._show_metrics()

    def __call__(self):
        asyncio.run(self._async_run())

    def _show_metrics(self):
        print("")
        self.metric_list.insert(0, self.execution_time)

        for metric in self.metric_list:
            metric.print_line()
        print("")

    async def on_start(self):
        raise NotImplementedError(
            "Method `on_start` not implemented. "
            + "Please create it with the following signature: "
            + "`async def on_start(self): ...`"
        )

    async def task(self):
        raise NotImplementedError(
            "Method `task` not implemented. "
            + "Please create it with the following signature: "
            + "`async def task(self): ...`"
        )

    async def on_end(self):
        raise NotImplementedError(
            "Method `on_end` not implemented. "
            + "Please create it with the following signature: "
            + "`async def on_end(self): ...`"
        )

    def metrics(self):
        raise NotImplementedError(
            "Method `metrics` not implemented. "
            + "Please create it with the following signature: "
            + "`def metrics(self): ...`"
        )

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
        cls._color_print(1, *args, **kwargs)

    @classmethod
    def info(cls, *args, **kwargs):
        cls._color_print(94, *args, **kwargs)

    @classmethod
    def warning(cls, *args, **kwargs):
        cls._color_print(93, *args, **kwargs)

    @classmethod
    def error(cls, *args, **kwargs):
        cls._color_print(91, *args, **kwargs)

    @classmethod
    def pprint(cls, *args, **kwargs):
        cls._color_pprint(94, *args, **kwargs)
