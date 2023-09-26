import asyncio
import time

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

        Metric("Test duration", self.duration, "s").print_line()
        Metric("Test rate", self.rate, "/s").print_line()
        print("")

        await self.on_start()

        start_time = time.time()
        await asyncio.gather(*self.tasks)
        end_time = time.time()

        await self.on_end()

        self.execution_time = Metric("Execution time", end_time - start_time, "s")

        self.metrics()
        self.show_metrics()

    def __call__(self):
        asyncio.run(self._async_run())

    def show_metrics(self):
        print("")
        for metric in self.metric_list:
            metric.print_line()
        print(f"\n{'.'*48}\n")

    async def on_start(self):
        raise NotImplementedError("Method `on_start` not implemented.")

    async def task(self):
        raise NotImplementedError("Method `task` not implemented.")

    async def on_end(self):
        raise NotImplementedError("Method `on_end` not implemented.")

    def metrics(self):
        raise NotImplementedError("Method `metrics` not implemented.")
