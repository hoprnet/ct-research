import logging
from typing import Optional

from prometheus_client import Gauge

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Channel, Session, SessionFailure
from core.components.address import Address
from core.components.logs import configure_logging
from core.components.session_to_socket import SessionToSocket

CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])
SESSION_OPS = Gauge(
    "ct_session_operation", "Session operation", ["source", "relayer", "op", "success"]
)


configure_logging()
logger = logging.getLogger(__name__)


class NodeHelper:
    @classmethod
    async def open_channel(cls, initiator: Address, api: HoprdAPI, address: str, amount: int):
        """
        Attempts to open a payment channel from the initiator to the specified address.
        
        Logs the operation, calls the API to open the channel with the given amount (converted to the smallest unit), and updates Prometheus metrics on success.
        """
        log_params = {"from": initiator.hopr, "to": address, "amount": amount}
        logger.debug("Opening channel", log_params)
        channel = await api.open_channel(address, f"{int(amount*1e18):d}")

        if channel is not None:
            logger.info("Opened channel", log_params)
            CHANNELS_OPS.labels(initiator.hopr, "opened").inc()
        else:
            logger.warning(f"Failed to open channel to {address}", log_params)

    @classmethod
    async def close_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, type: str):
        """
        Closes a specified channel and updates operation metrics.
        
        Attempts to close the given channel using the provided API. On success, logs the operation and increments the corresponding Prometheus metric labeled by channel type.
        """
        logs_params = {"from": initiator.hopr, "channel": channel.id}
        logger.debug(f"Closing {type} channel", logs_params)

        ok = await api.close_channel(channel.id)

        if ok:
            logger.info(f"Closed {type} channel", logs_params)
            CHANNELS_OPS.labels(initiator.hopr, type).inc()
        else:
            logger.warning(f"Failed to close {type}", logs_params)

    @classmethod
    async def fund_channel(cls, initiator: Address, api: HoprdAPI, channel: Channel, amount: int):
        """
        Funds an existing channel with a specified amount.
        
        Attempts to add funds to the given channel using the provided amount. Logs the operation and updates Prometheus metrics on success.
        """
        logs_params = {"from": initiator.hopr, "channel": channel.id, "amount": amount}
        logger.debug("Funding channel", logs_params)

        ok = await api.fund_channel(channel.id, amount * 1e18)

        if ok:
            logger.info("Funded channel", logs_params)
            CHANNELS_OPS.labels(initiator.hopr, "fund").inc()
        else:
            logger.warning("Failed to fund channel", logs_params)

    @classmethod
    async def open_session(
        cls, initiator: Address, api: HoprdAPI, relayer: str, listen_host: str
    ) -> Optional[Session]:
        """
        Attempts to open a session from the initiator to the specified relayer.
        
        If successful, returns the created Session object and updates Prometheus metrics; otherwise, logs the failure, updates metrics, and returns None.
        
        Args:
            initiator: The address initiating the session.
            relayer: The relayer node to connect to.
            listen_host: The host address to listen on.
        
        Returns:
            The created Session object if successful, or None if the session could not be opened.
        """
        logs_params = {
            "from": initiator.hopr,
            "relayer": relayer,
            "listen_host": listen_host,
        }
        logger.debug("Opening session", logs_params)

        session = await api.post_session(initiator.hopr, relayer, listen_host)
        match session:
            case Session():
                logger.debug("Opened session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(initiator.hopr, relayer, "opened", "yes").inc()
                return session
            case SessionFailure():
                logger.warning("Failed to open a session", {**logs_params, **session.as_dict})
                SESSION_OPS.labels(initiator.hopr, relayer, "opened", "no").inc()
                return None

    @classmethod
    async def close_session(
        cls,
        initiator: Address,
        api: HoprdAPI,
        relayer: str,
        sess_to_socket: SessionToSocket,
    ):
        """
        Closes an active session and updates metrics based on the outcome.
        
        Attempts to close the session associated with the provided session-to-socket mapping. On success, increments the corresponding Prometheus metric and closes the socket; on failure, logs a warning and updates the metric accordingly.
        """
        logs_params = {"from": initiator.hopr, "relayer": relayer}
        logger.debug("Closing the session", logs_params)

        ok = await api.close_session(sess_to_socket.session)

        if ok:
            logger.debug("Closed the session", logs_params)
            SESSION_OPS.labels(initiator.hopr, relayer, "closed", "yes").inc()
            sess_to_socket.socket.close()
        else:
            logger.warning("Failed to close the session", logs_params)
            SESSION_OPS.labels(initiator.hopr, relayer, "closed", "no").inc()

    @classmethod
    async def close_session_blindly(cls, initiator: Address, api: HoprdAPI, session: Session):
        """
        Closes a session without additional context or socket management.
        
        Attempts to close the specified session via the API and logs the outcome.
        """
        logs_params = {"from": initiator.hopr, "session": session.as_dict}
        logger.debug("Closing the session blindly", logs_params)

        ok = await api.close_session(session)

        if ok:
            logger.info("Closed the session blindly", logs_params)
        else:
            logger.warning("Failed to close the session blindly", logs_params)
