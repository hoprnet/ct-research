import asyncio
import logging

from tools import HoprdAPIHelper, envvar, getlogger

from . import EnduranceTest, Metric

log = getlogger()
log.setLevel(logging.ERROR)


class SendMessages(EnduranceTest):
    async def on_start(self):
        self.results = []

        self.api = HoprdAPIHelper(envvar("API_URL"), envvar("API_KEY"))
        self.recipient = await self.api.get_address("hopr")

        try:
            relayer_url = envvar("TEST_RELAYER_API_URL")
            relayer_key = envvar("TEST_RELAYER_API_KEY")
        except KeyError:
            self.print("No relayer configured, using relayer defined by `peer_id`")
            self.relayer = envvar("TEST_RELAYER_PEER_ID")
        else:
            relayer_api = HoprdAPIHelper(relayer_url, relayer_key)
            self.relayer = await relayer_api.get_address("hopr")

        await self.api.messages_pop_all(envvar("MESSAGE_TAG", int))
        self.print(
            f"Connected to node '...{self.recipient[-10:]}', "
            + f"with relayer '...{self.relayer[-10:]}'"
        )

    async def task(self) -> bool:
        success = await self.api.send_message(
            self.recipient,
            "Load testing",
            [self.relayer],
            envvar("MESSAGE_TAG", int),
        )

        self.results.append(success)

    async def on_end(self):
        sleep_time = 10

        self.print(f"Waiting {sleep_time}s for messages to be relayed")
        await asyncio.sleep(sleep_time)

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
        self.metric_list = [
            self.execution_time,
            expected_messages,
            issued_messages,
            relayed_messages,
            issuing_rate,
            delivery_rate,
            issuing_speed,
            delivery_speed,
        ]
