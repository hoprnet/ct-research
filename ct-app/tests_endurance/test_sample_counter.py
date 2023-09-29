from . import EnduranceTest, Metric


class SampleCounter(EnduranceTest):
    async def on_start(self):
        self.counter = 0

    async def task(self) -> bool:
        self.counter += 1

    async def on_end(self):
        pass

    def metrics(self):
        self.metric_list = [
            Metric("Counter", self.counter, cdt=f"== {self.duration * self.rate}")
        ]
