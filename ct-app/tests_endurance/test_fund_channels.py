import asyncio
import random

from tools import HoprdAPIHelper, envvar

from . import EnduranceTest, Metric


class FundChannels(EnduranceTest):
    async def on_start(self):
        self.results = []
        self.api = HoprdAPIHelper(envvar("API_URL"), envvar("API_KEY"))

        address = await self.api.get_address("hopr")
        self.info(f"Connected to node '...{address[-10:]}'")

        # get channel
        channels = await self.api.outgoing_channels(False)
        open_channels = [c for c in channels if c.status == "Open"]

        if len(open_channels) == 0:
            raise Exception("No open channels found")

        self.channel = random.choice(open_channels)
        self.inital_balance = self.channel.balance

        self.info(f"channel: {self.channel.id}", prefix="\t")
        self.info(f"balance: {self.inital_balance}", prefix="\t")

    async def task(self) -> bool:
        success = await self.api.fund_channel(self.channel.id, envvar("FUND_AMOUNT"))
        self.results.append(success)

    async def on_end(self):
        async def balance_changed(id: str, balance: str):
            while True:
                channels = await self.api.outgoing_channels(False)
                channel = channels[[c.id for c in channels].index(id)]
                if channel.balance != balance:
                    break

                await asyncio.sleep(0.1)

            return channel.balance

        timeout = envvar("BALANCE_CHANGE_TIMEOUT", float)
        self.info(f"Waiting up to {timeout}s for the balance to change")
        try:
            self.final_balance = await asyncio.wait_for(
                balance_changed(self.channel.id, self.inital_balance), timeout=timeout
            )
        except asyncio.TimeoutError:
            self.error(f"Balance not changed after {timeout}s")
            self.final_balance = self.inital_balance

    def metrics(self) -> list[Metric]:
        exp_fundings = Metric("Expected fundings", len(self.results), "x")
        initial_balance = Metric("Initial balance", self.inital_balance)

        final_balance = Metric(
            "Final balance", self.final_balance, cdt=f"!= {initial_balance.v}"
        )

        return [exp_fundings, initial_balance, final_balance]
