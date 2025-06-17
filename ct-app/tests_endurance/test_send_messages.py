import asyncio
import logging
import random
from typing import Tuple

from core.api import HoprdAPI
from core.components import EnvironmentUtils
from core.components.logs import configure_logging

from . import EnduranceTest, Metric

CHARS = "0123456789abcdefghijklmnopqrstuvwxyz "

configure_logging()
logger = logging.getLogger(__name__)
logging.getLogger("core.api.hoprd_api").setLevel(logging.WARNING)


class SendMessages(EnduranceTest):
    async def on_start(self):
        self.results = []
        self.tag = random.randint(0, 2**16 - 1)

        self.api = HoprdAPI(EnvironmentUtils.envvar("API_URL"), EnvironmentUtils.envvar("API_KEY"))
        self.recipient = await self.api.address()

        channels = await self.api.channels()
        open_channels = [
            c for c in channels.all if c.source == self.recipient.native and c.status.is_open
        ]

        if len(open_channels) == 0:
            raise Exception("No open channels found")

        selected_address = EnvironmentUtils.envvar("RELAYER_ADDRESS")

        if selected_address is not None:
            channel = [c for c in open_channels if c.destination == selected_address][0]
        else:
            channel = random.choice(open_channels)

        self.relayer = channel.destination
        self.message_tag = random.randint(1024, 32768)

        logger.info(f"Connected to node {self.recipient.native}")
        logger.info(f"\trelayer: {self.relayer}")
        logger.info(f"\tchannel: {channel.id}")
        logger.info(f"\tstatus : {channel.status}")
        logger.info(f"\tbalance: {channel.balance}HOPR")
        logger.info(f"\ttag    : {self.tag}")

        await self.api.messages_pop_all(self.message_tag)

    async def task(self):
        success = await self.api.send_message(
            self.recipient.native,
            "".join(random.choices(CHARS, k=random.randint(10, 30))),
            [self.relayer],
            self.message_tag,
        )

        self.results.append(success is not None)

    async def on_end(self):
        sleep_time = EnvironmentUtils.envvar("DELAY_BEFORE_INBOX_CHECK", type=float)

        if sum(self.results) > 0:
            logger.info(f"Waiting {sleep_time}s for messages to be relayed")
            await asyncio.sleep(sleep_time)
        else:
            logger.warning("No messages were relayed, skipping wait")

        inbox = await self.api.messages_pop_all(
            self.message_tag,
        )
        self.inbox_size = len(inbox)

    def success_flag(self) -> Tuple[bool, str]:
        return sum(self.results) / len(self.results) >= 0.9, ""

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
