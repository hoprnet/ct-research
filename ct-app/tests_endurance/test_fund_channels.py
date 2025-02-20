import asyncio
import logging
import random

from core.api import HoprdAPI
from core.components import EnvironmentUtils
from core.components.logs import configure_logging

from . import EnduranceTest, Metric

configure_logging()
logger = logging.getLogger(__name__)


class FundChannels(EnduranceTest):
    async def on_start(self):
        self.results = []
        self.api = HoprdAPI(
            EnvironmentUtils.envvar(
                "API_URL"), EnvironmentUtils.envvar("API_KEY")
        )

        self.address = await self.api.get_address()
        logger.info(f"Connected to node '...{self.address.hopr[-10:]}'")

        # get channel
        channels = await self.api.channels()
        open_channels = [
            c
            for c in channels
            if c.status.is_open and c.source_peer_id == self.address.hopr
        ]

        if len(open_channels) == 0:
            raise RuntimeError("No open channels found")

        self.channel = random.choice(open_channels)
        self.inital_balance = self.channel.balance

        logger.info(f"peer_id: {self.channel.peer_id}", prefix="\t")
        logger.info(f"channel: {self.channel.id}", prefix="\t")
        logger.info(f"balance: {self.inital_balance}", prefix="\t")

    async def task(self) -> bool:
        success = await self.api.fund_channel(
            self.channel.id, EnvironmentUtils.envvar("FUND_AMOUNT")
        )
        self.results.append(success)

    async def on_end(self):
        async def balance_changed(id: str, balance: str):
            while True:
                channels = await self.api.channels()
                channel = channels[
                    [
                        c.id for c in channels if c.source_peer_id == self.address.hopr
                    ].index(id)
                ]
                if channel.balance != balance:
                    break

                await asyncio.sleep(0.1)

            return channel.balance

        timeout = EnvironmentUtils.envvar("BALANCE_CHANGE_TIMEOUT", float)
        logger.info(f"Waiting up to {timeout}s for the balance to change")
        try:
            self.final_balance = await asyncio.wait_for(
                balance_changed(self.channel.id, self.inital_balance), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Balance not changed after {timeout}s")
            self.final_balance = self.inital_balance

    def metrics(self) -> list[Metric]:
        exp_fundings = Metric("Expected fundings", len(self.results), "x")
        initial_balance = Metric("Initial balance", self.inital_balance)

        final_balance = Metric(
            "Final balance", self.final_balance, cdt=f"!= {initial_balance.v}"
        )

        return [exp_fundings, initial_balance, final_balance]
