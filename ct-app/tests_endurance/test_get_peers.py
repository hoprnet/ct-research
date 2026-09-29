import logging
from typing import Tuple

from api_lib.headers.authorization import Bearer

from core.api import HoprdAPI

from . import EnduranceTest, EnvironmentUtils, Metric

logger = logging.getLogger(__name__)


class GetPeers(EnduranceTest):
    async def on_start(self):
        self.results = []

        self.api = HoprdAPI(
            EnvironmentUtils.envvar("API_URL"),
            Bearer(EnvironmentUtils.envvar("API_KEY")),
            "/api/v4",
        )
        self.recipient = await self.api.address()
        logger.info(f"Connected to node {self.recipient.native}")

    async def task(self):
        success = await self.api.peers() is not None

        self.results.append(success)

    def success_flag(self) -> Tuple[bool, str]:
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
