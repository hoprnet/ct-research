import logging

from core.api import HoprdAPI
from core.components import EnvironmentUtils
from core.components.logs import configure_logging

from . import EnduranceTest, Metric

configure_logging()
logger = logging.getLogger(__name__)


class GetChannels(EnduranceTest):
    async def on_start(self):
        """
        Initializes the test by setting up result tracking and connecting to the API node.
        
        Creates an empty list to store test results, initializes the API client using environment variables, retrieves the node address asynchronously, and logs the connected node's identifier.
        """
        self.results = []

        self.api = HoprdAPI(EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY"))
        self.recipient = await self.api.get_address()
        logger.info(f"Connected to node {self.recipient.hopr}")

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
