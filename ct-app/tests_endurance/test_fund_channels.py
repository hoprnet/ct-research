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
        """
        Initializes the test by connecting to the API, retrieving the node address, and selecting a random open channel.
        
        Raises:
            RuntimeError: If no open channels are found for the node.
        """
        self.results = []
        self.api = HoprdAPI(EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY"))

        self.address = await self.api.get_address()
        logger.info(f"Connected to node '...{self.address.hopr[-10:]}'")

        # get channel
        channels = await self.api.channels()
        open_channels = [
            c for c in channels if c.status.is_open and c.source_peer_id == self.address.hopr
        ]

        if len(open_channels) == 0:
            raise RuntimeError("No open channels found")

        self.channel = random.choice(open_channels)
        self.inital_balance = self.channel.balance

        logger.info(f"\tpeer_id: {self.channel.peer_id}")
        logger.info(f"\tchannel: {self.channel.id}")
        logger.info(f"\tbalance: {self.inital_balance}")

    async def task(self) -> bool:
        success = await self.api.fund_channel(
            self.channel.id, EnvironmentUtils.envvar("FUND_AMOUNT")
        )
        self.results.append(success)

    async def on_end(self):
        """
        Waits for the selected channel's balance to change, updating the final balance or timing out.
        
        If the channel's balance does not change within the specified timeout, sets the final balance to the initial balance.
        """
        async def balance_changed(id: str, balance: str):
            while True:
                channels = await self.api.channels()
                channel = channels[
                    [c.id for c in channels if c.source_peer_id == self.address.hopr].index(id)
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
        """
        Returns a list of metrics summarizing the number of fundings and channel balances.
        
        The metrics include the expected number of fundings, the initial channel balance, and the final channel balance, with a condition that the final balance should differ from the initial balance.
        """
        exp_fundings = Metric("Expected fundings", len(self.results), "x")
        initial_balance = Metric("Initial balance", self.inital_balance)

        final_balance = Metric("Final balance", self.final_balance, cdt=f"!= {initial_balance.v}")

        return [exp_fundings, initial_balance, final_balance]
