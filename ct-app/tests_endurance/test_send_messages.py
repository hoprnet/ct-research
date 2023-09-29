import asyncio
import random

from tools import HoprdAPIHelper, envvar

from . import EnduranceTest, Metric


class SendMessages(EnduranceTest):
    async def on_start(self):
        self.results = []

        self.api = HoprdAPIHelper(envvar("API_URL"), envvar("API_KEY"))
        self.recipient = await self.api.get_address("hopr")

        channels = await self.api.all_channels(False)
        open_channels = [
            c
            for c in channels.all
            if c.source_peer_id == self.recipient and c.status == "Open"
        ]

        if len(open_channels) == 0:
            raise Exception("No open channels found")

        channel = random.choice(open_channels)

        self.relayer = channel.destination_peer_id

        self.info(f"Connected to node {self.recipient}")
        self.info(f"relayer: {self.relayer}", prefix="\t")
        self.info(f"channel: {channel.channel_id}", prefix="\t")
        self.info(f"status : {channel.status}", prefix="\t")
        self.info(f"balance: {channel.balance}HOPR", prefix="\t")

        await self.api.messages_pop_all(envvar("MESSAGE_TAG", int))

    async def task(self) -> bool:
        success = await self.api.send_message(
            self.recipient,
            "Load testing",
            [self.relayer],
            envvar("MESSAGE_TAG", int),
        )

        self.results.append(success)

    async def on_end(self):
        sleep_time = envvar("DELAY_BEFORE_INBOX_CHECK", float)

        if sum(self.results) > 0:
            self.info(f"Waiting {sleep_time}s for messages to be relayed")
            await asyncio.sleep(sleep_time)
        else:
            self.warning("No messages were relayed, skipping wait")

        inbox = await self.api.messages_pop_all(envvar("MESSAGE_TAG", int))
        self.inbox_size = len(inbox)

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
