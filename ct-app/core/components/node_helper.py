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
        """
        Open a new UDP session for message relay.

        Creates a session at the API level, which allocates a UDP port for
        communication. The session allows messages to be relayed through a
        specific peer (relayer) to reach the destination.

        Args:
            api: HOPR node API client
            destination: Target peer address to relay messages to
            relayer: Intermediate peer address that will relay the messages
            listen_host: Local IP address for socket binding (usually "127.0.0.1")

        Returns:
            Session object if successful, None if API call failed

        Metrics:
            Updates SESSION_OPS Prometheus gauge with success/failure:
            - SESSION_OPS{relayer="...", op="opened", success="yes"}
            - SESSION_OPS{relayer="...", op="opened", success="no"}

        Note:
            After calling this, you must call session.create_socket() to
            establish the local UDP socket connection.

        Example:
            >>> session = await NodeHelper.open_session(
            ...     api, "peer_dest", "peer_relay", "127.0.0.1"
            ... )
            >>> if session:
            ...     session.create_socket()
        """
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
        """
        Close a UDP session at the API level.

        Attempts to close the session via API call. The return value indicates
        whether the API close succeeded, which is important for detecting orphaned
        sessions when the API close fails but local cleanup proceeds.

        Args:
            api: HOPR node API client
            session: Session object to close
            relayer: Peer address for logging and metrics (optional)

        Returns:
            bool: True if API close succeeded, False otherwise

        Behavior:
            - Calls api.close_session() to close at API level
            - Logs success/failure
            - Updates SESSION_OPS metrics if relayer provided
            - Returns status for caller to decide on local cleanup

        Important:
            The caller should ALWAYS close the socket locally (session.close_socket())
            even if this returns False, to prevent resource leaks. The return value
            helps detect orphaned sessions where local state is cleaned but API
            session remains.

        Metrics:
            Updates SESSION_OPS if relayer is provided:
            - SESSION_OPS{relayer="...", op="closed", success="yes"}
            - SESSION_OPS{relayer="...", op="closed", success="no"}

        Example:
            >>> ok = await NodeHelper.close_session(api, session, "peer_1")
            >>> if not ok:
            ...     logger.warning("Session may be orphaned at API level")
            >>> session.close_socket()  # Always close locally
        """
        logs_params = {"relayer": relayer if relayer else ""}

        logger.debug("Closing the session", logs_params)

        ok = await api.close_session(session)

        if ok:
            logger.info("Closed the session", logs_params)
        else:
            logger.warning("Failed to close the session", logs_params)

        if relayer:
            SESSION_OPS.labels(relayer, "closed", "yes" if ok else "no").inc()

        return ok

    @classmethod
    async def send_batch_messages(cls, session: Session, message: MessageFormat):
        """
        Send a batch of messages and wait for responses.

        Sends multiple copies of the same message through a session and waits
        for all responses. This is typically called as a background task via
        AsyncLoop.add() with publish_to_task_set=False.

        Args:
            session: Active session to send messages through
            message: MessageFormat object containing message data and batch settings

        Behavior:
            1. Sends message.batch_size copies of the message
            2. Waits to receive responses (total size = batch_size * packet_size)
            3. Handles timeouts and partial receives gracefully

        Background Task Pattern:
            This method is designed to run as a fire-and-forget background task:
            >>> AsyncLoop.add(
            ...     NodeHelper.send_batch_messages,
            ...     session_ref,
            ...     message,
            ...     publish_to_task_set=False
            ... )

            Using publish_to_task_set=False prevents the main loop from waiting
            on these operations, allowing concurrent message sending.

        Thread Safety:
            Safe to call concurrently for different sessions. Each session has
            its own socket, and we use session_ref from observe_message_queue()
            to avoid accessing the shared sessions dict during background execution.

        Note:
            Exceptions are logged by AsyncLoop but don't crash the main process.
        """
        for _ in range(message.batch_size):
            session.send(message)
        await session.receive(message.packet_size, message.batch_size * message.packet_size)
