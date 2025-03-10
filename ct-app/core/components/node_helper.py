import logging

from prometheus_client import Gauge

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Channel
from core.components.address import Address
from core.components.logs import configure_logging
from core.components.messages.message_format import MessageFormat

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])


configure_logging()
logger = logging.getLogger(__name__)


class NodeHelper:
    @classmethod
    async def open_channel(
        cls, initiator: Address, api: HoprdAPI, address: str, amount: int
    ):
        logger.debug(
            "Opening channel", {"from": initiator.hopr, "to": address, "amount": amount}
        )
        channel = await api.open_channel(address, f"{int(amount*1e18):d}")

        if channel is not None:
            logger.info(f"Opened channel to {address}")
            CHANNELS_OPS.labels(initiator.hopr, "opened").inc()
        else:
            logger.warning(f"Failed to open channel to {address}")

    @classmethod
    async def close_pending_channel(
        cls, initiator: Address, api: HoprdAPI, channel: Channel
    ):
        logger.debug(
            "Closing pending channel", {"from": initiator.hopr, "channel": channel.id}
        )
        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed pending channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "pending_closed").inc()
        else:
            logger.warning(f"Failed to close pending channel {channel.id}")

    @classmethod
    async def close_incoming_channel(
        cls, initiator: Address, api: HoprdAPI, channel: Channel
    ):
        logger.debug(
            "Closing incoming channel", {"from": initiator.hopr, "channel": channel.id}
        )
        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "incoming_closed").inc()
        else:
            logger.warning(f"Failed to close channel {channel.id}")

    @classmethod
    async def close_old_channel(
        cls, initiator: Address, api: HoprdAPI, channel_id: str
    ):
        logger.debug("Closing channel", {"from": initiator.hopr, "channel": channel_id})
        ok = await api.close_channel(channel_id)

        if ok:
            logger.info(f"Channel closed {channel_id} ")
            CHANNELS_OPS.labels(initiator.hopr, "old_closed").inc()
        else:
            logger.warning(f"Failed to close channel {channel_id}")

    @classmethod
    async def fund_channel(
        cls, initiator: Address, api: HoprdAPI, channel: Channel, amount: int
    ):
        logger.debug(
            "Funding channel",
            {"from": initiator.hopr, "channel": channel.id, "amount": amount},
        )
        ok = await api.fund_channel(channel.id, amount * 1e18)

        if ok:
            logger.info(f"Funded channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "fund").inc()
        else:
            logger.warning(f"Failed to fund channel {channel.id}")

    @classmethod
    async def send_message(
        cls, initiator: Address, api: HoprdAPI, message: MessageFormat
    ):
        for idx in range(message.multiplier):
            await api.send_message(initiator.hopr, message.format(), [message.relayer])
            message.increase_inner_index()
