from prometheus_client import Gauge

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Channel
from core.components.address import Address

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])

class NodeHelper:
    @classmethod
    async def open_channel(cls, initiator: Address, api: HoprdAPI, address: str, amount: int):
        cls().debug(f"Opening channel from {initiator} to {address}")
        channel = await api.open_channel(address, f"{int(amount*1e18):d}")

        if channel is not None:
            cls().info(f"Opened channel to {address}")
            CHANNELS_OPS.labels(initiator.hopr, "opened").inc()
        else:
            cls().warning(f"Failed to open channel to {address}")

    @classmethod
    async def close_pending_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel):
        cls().debug(f"Closing pending channel from {initiator}: {channel.id}")
        ok = await api.close_channel(channel.id)

        if ok:
            cls().info(f"Closed pending channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "pending_closed").inc()
        else:
            cls().warning(f"Failed to close pending channel {channel.id}")

    @classmethod
    async def close_incoming_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel):
        cls().debug(f"Closing incoming channel to {initiator}: {channel.id}")
        ok = await api.close_channel(channel.id)

        if ok:
            cls().info(f"Closed channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "incoming_closed").inc()
        else:
            cls().warning(f"Failed to close channel {channel.id}")

    @classmethod
    async def close_old_channel(cls, initiator: Address, api: HoprdAPI, channel_id: str):
        cls().debug(f"Closing channel from {initiator}: {channel_id}")
        ok = await api.close_channel(channel_id)

        if ok:
            cls().info(f"Channel closed {channel_id} ")
            CHANNELS_OPS.labels(initiator.hopr, "old_closed").inc()
        else:
            cls().warning(f"Failed to close channel {channel_id}")

    @classmethod
    async def fund_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, amount: int):
        cls().debug(f"Funding channel from {initiator}: {channel.id}")
        ok = await api.fund_channel(channel.id, amount * 1e18)

        if ok:
            cls().info(f"Funded channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "fund").inc()
        else:
            cls().warning(f"Failed to fund channel {channel.id}")