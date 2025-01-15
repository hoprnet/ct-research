from core.api import HoprdAPI
from core.components import EnvironmentUtils

from . import EnduranceTest, Metric


class GetChannels(EnduranceTest):
    async def on_start(self):
        self.results = []

        self.api = HoprdAPI(
            EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY")
        )
        self.recipient = await self.api.get_address()
        self.info(f"Connected to node {self.recipient.hopr}")

    async def task(self) -> bool:
        success = await self.api.channels() is not None

        self.results.append(success)

    async def on_end(self):
        pass

    def success_flag(self) -> bool:
        return sum(self.results) / len(self.results) >= 0.9, ""

    def metrics(self):
        # Messages counts
        expected_calls = Metric(
            "Expected calls",
            len(self.results),
        )

        successful_calls = Metric(
            "Successful calls",
            sum(self.results),
        )

        # Export metrics
        return [
            expected_calls,
            successful_calls,
        ]
