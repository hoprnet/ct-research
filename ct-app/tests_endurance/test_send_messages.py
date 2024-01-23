import asyncio
import random

from core.components.hoprd_api import HoprdAPI
from core.components.utils import EnvironmentUtils

from . import EnduranceTest, Metric


class SendMessages(EnduranceTest):
    async def on_start(self):
        self.results = []
        self.tag = random.randint(0, 2**16 - 1)

        self.api = HoprdAPI(
            EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY")
        )
        self.recipient = await self.api.get_address("hopr")

        channels = await self.api.all_channels(False)
        open_channels = [
            c
            for c in channels.all
            if c.source_peer_id == self.recipient and c.status == "Open"
        ]

        if len(open_channels) == 0:
            raise Exception("No open channels found")

        self.relayer = EnvironmentUtils.envvar("RELAYER_PEER_ID", None)
        if self.relayer is None:
            channel = random.choice(open_channels)
            self.relayer = channel.destination_peer_id
        else:
            channel = next(
                (c for c in open_channels if c.destination_peer_id == self.relayer),
                None,
            )
            if channel is None:
                raise Exception("Channel not found")

        self.info(f"Connected to node {self.recipient}")
        self.info(f"relayer: {self.relayer}", prefix="\t")
        self.info(f"channel: {channel.channel_id}", prefix="\t")
        self.info(f"status : {channel.status}", prefix="\t")
        self.info(f"balance: {channel.balance}HOPR", prefix="\t")
        self.info(f"tag    : {self.tag}", prefix="\t")

        await self.api.messages_pop_all(self.tag)

    async def task(self) -> bool:
        success = await self.api.send_message(
            self.recipient, "Load testing", [self.relayer], self.tag
        )

        self.results.append(success)

    async def on_end(self):
        sleep_time = EnvironmentUtils.envvar("DELAY_BEFORE_INBOX_CHECK", type=float)

        if sum(self.results) > 0:
            self.info(f"Waiting {sleep_time}s for messages to be relayed")
            await asyncio.sleep(sleep_time)
        else:
            self.warning("No messages were relayed, skipping wait")

        inbox = await self.api.messages_pop_all(self.tag)
        self.inbox_size = len(inbox)

    def success_flag(self) -> bool:
        return (
            abs(1 - self.execution_time.v / self.duration) <= 0.1,
            f"Execution time differs from expected duration by more than 10% ({self.execution_time.v:.2f} !~ {self.duration:.2f})",
        )

    def metrics(self):
        # Messages counts
        expected_messages = Metric(
            "Expected messages",
            len(self.results),
        )

        issued_messages = Metric(
            "Issued messages",
            sum(self.results),
            cdt=f"== {expected_messages.v}",
        )

        relayed_messages = Metric(
            "Relayed messages",
            self.inbox_size,
            cdt=f"== {expected_messages.v}",
        )

        # Issuing and delivery rate
        issuing_rate = Metric(
            "Issuing rate",
            issued_messages.v / expected_messages.v * 100,
            "%",
            cdt=">= 90",
        )
        delivery_rate = Metric(
            "Delivery rate",
            relayed_messages.v / expected_messages.v * 100,
            "%",
            cdt=">= 90",
        )

        # Issuing and delivery speed
        issuing_speed = Metric(
            "Issuing speed",
            issued_messages.v / self.execution_time.v,
            "msg/s",
            cdt=f">= {0.9*self.rate}",
        )
        delivery_speed = Metric(
            "Delivery speed",
            relayed_messages.v / self.execution_time.v,
            "msg/s",
            cdt=f">= {0.9*self.rate}",
        )

        # Export metrics
        return [
            expected_messages,
            issued_messages,
            relayed_messages,
            issuing_rate,
            delivery_rate,
            issuing_speed,
            delivery_speed,
        ]
