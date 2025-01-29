from re import U
from typing import Optional

from prometheus_client import Gauge

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Channel, Session
from core.baseclass import Base
from core.components.address import Address

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])
SESSION_OPS = Gauge("ct_session_operation", "Session operation", ["source", "relayer", "op", "success"])

class NodeHelper(Base):
    @classmethod
    async def open_channel(cls, initiator: Address, api: HoprdAPI, address: str, amount: int):
        cls().debug(f"Opening channel from {initiator} to {address}")
        channel = await api.open_channel(address, f"{int(amount*1e18):d}")

        if channel is not None:
            cls().info(f"Opened channel to {address}")
            CHANNELS_OPS.labels(initiator.hopr, "opened").inc()
        else:
            cls().warning(f"Failed to open channel from {initiator} to {address}")

    @classmethod
    async def close_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, label: str):
        cls().debug(
            f"Closing channel from {initiator}: {channel.id} with label '{label}'")
        ok = await api.close_channel(channel.id)

        if ok:
            cls().info(f"Closed channel {channel.id}  with label '{label}'")
            CHANNELS_OPS.labels(initiator.hopr, label).inc()
        else:
            cls().warning(f"Failed to close channel {channel.id} with label '{label}'")

    @classmethod
    async def fund_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, amount: int):
        cls().debug(f"Funding channel from {initiator}: {channel.id}")
        ok = await api.fund_channel(channel.id, amount * 1e18)

        if ok:
            cls().info(f"Funded channel {channel.id}")
            CHANNELS_OPS.labels(initiator.hopr, "fund").inc()
        else:
            cls().warning(f"Failed to fund channel {channel.id}")


    @classmethod
    async def open_session(cls, initiator: Address, api: HoprdAPI, relayer: Address) -> Optional[Session]:
        cls().debug(f"Opening session from {initiator} for {relayer}")
        session = await api.post_session(initiator.hopr, relayer.hopr)
        
        if session is not None:
            cls().debug(f"Opened session from {initiator} for {relayer}")
            SESSION_OPS.labels(initiator.hopr, relayer.hopr, "opened", "yes").inc()
        else:
            cls().warning(f"Failed to open a session from {initiator} for {relayer}")
            SESSION_OPS.labels(initiator.hopr, relayer.hopr, "opened", "no").inc()

        return session

    @classmethod
    async def close_session(cls, initiator: Address, api: HoprdAPI, relayer:Address, session: Session):
        cls().debug(f"Closing the session from {initiator} for {relayer}")
        ok = await api.close_session(session)

        if ok:
            cls().debug(f"Closed the session from {initiator} for {relayer}")
            SESSION_OPS.labels(initiator.hopr, relayer.hopr, "closed", "yes").inc()
        else:
            cls().warning(f"Failed to close the session from {initiator} for {relayer}")
            SESSION_OPS.labels(initiator.hopr, relayer.hopr, "closed", "no").inc()

    
