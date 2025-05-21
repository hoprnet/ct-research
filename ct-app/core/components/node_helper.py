import logging
from typing import Optional

from prometheus_client import Gauge

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Channel, Session, SessionFailure
from core.components.address import Address
from core.components.logs import configure_logging
from core.components.session_to_socket import SessionToSocket

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["address", "op"])
SESSION_OPS = Gauge(
    "ct_session_operation", "Session operation", ["source", "relayer", "op", "success"]
)


configure_logging()
logger = logging.getLogger(__name__)


class NodeHelper:
    @classmethod
    async def open_channel(cls, initiator: Address, api: HoprdAPI, address: str, amount: int):
        log_params = {"from": initiator.native, "to": address, "amount": amount}
        logger.debug("Opening channel", log_params)
        channel = await api.open_channel(address, f"{int(amount*1e18):d}")

        if channel is not None:
            logger.info("Opened channel", log_params)
            CHANNELS_OPS.labels(initiator.native, "opened").inc()
        else:
            logger.warning(f"Failed to open channel to {address}", log_params)

    @classmethod
    async def close_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, type: str):
        logs_params = {"from": initiator.native, "channel": channel.id}
        logger.debug(f"Closing {type} channel", logs_params)

        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed {type} channel", logs_params)
            CHANNELS_OPS.labels(initiator.native, type).inc()
        else:
            logger.warning(f"Failed to close {type}", logs_params)

    @classmethod
    async def fund_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, amount: int):
        logs_params = {"from": initiator.native, "channel": channel.id, "amount": amount}
        logger.debug("Funding channel", logs_params)

        ok = await api.fund_channel(channel.id, amount * 1e18)

        if ok:
            logger.info("Funded channel", logs_params)
            CHANNELS_OPS.labels(initiator.native, "fund").inc()
        else:
            logger.warning("Failed to fund channel", logs_params)

    @classmethod
    async def open_session(
        cls, initiator: Address, api: HoprdAPI, destination: Address, relayer: str, listen_host: str
    ) -> Optional[Session]:
        logs_params = {
            "from": initiator.native,
            "to": destination.native,
            "relayer": relayer,
            "listen_host": listen_host,
        }
        logger.debug("Opening session", logs_params)

        session = await api.post_session(destination.native, relayer, listen_host)
        match session:
            case Session():
                logger.debug("Opened session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(initiator.native, relayer, "opened", "yes").inc()
                return session
            case SessionFailure():
                logger.warning("Failed to open a session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(initiator.native, relayer, "opened", "no").inc()
                return None

    @classmethod
    async def close_session(
        cls,
        initiator: Address,
        api: HoprdAPI,
        relayer: str,
        sess_to_socket: SessionToSocket,
    ):
        logs_params = {"from": initiator.native, "relayer": relayer}
        logger.debug("Closing the session", logs_params)

        ok = await api.close_session(sess_to_socket.session)

        if ok:
            logger.debug("Closed the session", logs_params)
            SESSION_OPS.labels(initiator.native, relayer, "closed", "yes").inc()
            if socket := sess_to_socket.socket:
                socket.close()
        else:
            logger.warning("Failed to close the session", logs_params)
            SESSION_OPS.labels(initiator.native, relayer, "closed", "no").inc()

    @classmethod
    async def close_session_blindly(cls, initiator: Address, api: HoprdAPI, session: Session):
        logs_params = {"from": initiator.native, "session": session.as_dict}
        logger.debug("Closing the session blindly", logs_params)

        ok = await api.close_session(session)

        if ok:
            logger.info("Closed the session blindly", logs_params)
        else:
            logger.warning("Failed to close the session blindly", logs_params)
