from core.components import EnvironmentUtils
from core.components.hoprd_api import HoprdAPI

from . import EnduranceTest, Metric


class GetChannels(EnduranceTest):
    async def on_start(self):
        self.results = []

        self.api = HoprdAPI(
            EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY")
        )
        self.recipient = await self.api.get_address("hopr")
        self.info(f"Connected to node {self.recipient}")

    async def task(self) -> bool:
        success = await self.api.all_channels(False) is not None

        self.results.append(success)

    async def on_end(self):
        pass

    def success_flag(self) -> bool:
        return sum(self.results) / len(self.results) >= 0.9, ""

    def metrics(self):
        # Messages counts
        succesfull_queries = Metric(
            "Expected messages",
            len(self.results),
        )

        # Export metrics
        return [
            succesfull_queries,
        ]
