import logging
from typing import Optional

from prometheus_client import Gauge

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channel, Session, SessionFailure
from ..components.messages.message_format import MessageFormat
from .balance import Balance
from .logs import configure_logging

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["op", "success"])
SESSION_OPS = Gauge("ct_session_operation", "Session operation", ["relayer", "op", "success"])


configure_logging()
logger = logging.getLogger(__name__)


class NodeHelper:
    @classmethod
    async def open_channel(cls, api: HoprdAPI, address: str, amount: Balance):
        log_params = {"to": address, "amount": amount.as_str}
        logger.debug("Opening channel", log_params)
        channel = await api.open_channel(address, amount)

        if channel is not None:
            logger.info("Opened channel", log_params)
        else:
            logger.warning(f"Failed to open channel to {address}", log_params)
        CHANNELS_OPS.labels("opened", "yes" if channel else "no").inc()

    @classmethod
    async def close_channel(cls, api: HoprdAPI, channel: Channel, type: str):
        logs_params = {"channel": channel.id}
        logger.debug(f"Closing {type} channel", logs_params)

        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed {type} channel", logs_params)
        else:
            logger.warning(f"Failed to close {type}", logs_params)
        CHANNELS_OPS.labels(type, "yes" if ok else "no").inc()

    @classmethod
    async def fund_channel(cls, api: HoprdAPI, channel: Channel, amount: Balance):
        logs_params = {"channel": channel.id, "amount": amount.as_str}
        logger.debug("Funding channel", logs_params)

        ok = await api.fund_channel(channel.id, amount)

        if ok:
            logger.info("Fund channel", logs_params)
        else:
            logger.warning("Failed to fund channel", logs_params)
        CHANNELS_OPS.labels("fund", "yes" if ok else "no").inc()

    @classmethod
    async def open_session(
        cls, api: HoprdAPI, destination: str, relayer: str, listen_host: str
    ) -> Optional[Session]:
        logs_params = {
            "to": destination,
            "relayer": relayer,
        }
        logger.debug("Opening session", logs_params)

        session = await api.post_udp_session(destination, relayer, listen_host)
        match session:
            case Session():
                logger.info("Opened session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(relayer, "opened", "yes").inc()
                return session
            case SessionFailure():
                logger.warning("Failed to open a session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(relayer, "opened", "no").inc()
                return None

    @classmethod
    async def close_session(
        cls,
        api: HoprdAPI,
        session: Session,
        relayer: Optional[str] = None,
    ):
        logs_params = {"relayer": relayer if relayer else ""}

        logger.debug("Closing the session", logs_params)

        ok = await api.close_session(session)

        if ok:
            logger.info("Closed the session", logs_params)
        else:
            logger.warning("Failed to close the session", logs_params)

        if relayer:
            SESSION_OPS.labels(relayer, "closed", "yes" if ok else "no").inc()

    @classmethod
    async def send_batch_messages(cls, session: Session, message: MessageFormat):
        [session.send(message) for _ in range(message.batch_size)]
        await session.receive(message.packet_size, message.batch_size * message.packet_size)
