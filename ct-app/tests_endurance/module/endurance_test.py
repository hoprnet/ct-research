import asyncio
import pprint
import time
from datetime import timedelta

from .metric import Metric


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

    async def progress_bar(self):
        """
        Continuously check the state of tasks in self.tasks, and print the number of
        completed tasks.
        """
        _bar_length = 60

        while True:
            await asyncio.sleep(0.05)

            completed_tasks = sum(task.done() for task in self.tasks)

            hash_count = int(completed_tasks / (len(self.tasks) - 1) * _bar_length)
            dash_count = _bar_length - hash_count
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

        self.metrics()
        self._show_metrics()

    def __call__(self):
        asyncio.run(self._async_run())

    def info(self, *args, **kwargs):
        print("\033[94m[+] ", end="")
        print(*args, **kwargs)
        print("\033[0m", end="")

    def warning(self, *args, **kwargs):
        # print the message with all passed parameters, but in orange
        print("\033[93m[+] ", end="")
        print(*args, **kwargs)
        print("\033[0m", end="")

    def error(self, *args, **kwargs):
        print("\033[91m[+] ", end="")
        print(*args, **kwargs)
        print("\033[0m", end="")

    def pprint(self, *args, **kwargs):
        # print the message with all passed parameters, but in green
        print("\033[94m[+] ", end="")
        pprint.pprint(*args, **kwargs)
        print("\033[0m", end="")
        # reset the terminal to its default color

    def _show_metrics(self):
        print("")
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
