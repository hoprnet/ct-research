import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

from prometheus_client import Counter

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Session, SessionFailure
from ..api.session import DEFAULT_RECEIVE_TIMEOUT_SECONDS
from ..constants.labels import MessageSendFailureReason
from ..messages.message_metrics import (
    MESSAGE_E2E_LATENCY,
    MESSAGES_SENT_FAILED,
    MESSAGES_SENT_SUCCESS,
)
from ..services.burst_plan import packets_per_burst, send_rate
from ..types.message_format import MessageFormat

SESSION_OPS = Counter("ct_session_operation", "Session operation", ["relayer", "op", "success"])

logger = logging.getLogger(__name__)

# How often the burst sender wakes up to send the packets that became due.
BURST_PACING_TICK_SECONDS = 0.005


@dataclass(frozen=True)
class BurstResult:
    sent: int
    echoed: int


class NodeHelper:
    @staticmethod
    def _success_label(value) -> str:
        return "yes" if value else "no"

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

        session = await api.post_udp_session(destination, relayer=relayer, listen_host=listen_host)
        match session:
            case Session():
                logger.info("Opened session", session.as_dict)
                SESSION_OPS.labels(relayer, "opened", "yes").inc()
                return session
            case SessionFailure():
                logger.warning("Failed to open a session", session.as_dict)
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
            SESSION_OPS.labels(relayer, "closed", cls._success_label(ok)).inc()

        return ok

    @classmethod
    async def send_burst(
        cls,
        session: Session,
        message: MessageFormat,
        burst_rate: float,
        burst_duration: float,
        receive_timeout: float = DEFAULT_RECEIVE_TIMEOUT_SECONDS,
    ) -> BurstResult:
        """
        Send one burst through a session and count the packets echoed back.

        `burst_rate` (Mbit/s) is what the relayer forwards: every packet crosses it twice, out and
        back as its echo, so packets are paced evenly at half that rate over `burst_duration`
        seconds. The rate counts whole packets of `session.mtu` bytes, because the SURB rides in
        every packet, while each packet carries `message.packet_size` (MTU minus SURB) bytes of
        generated data.

        Echoes are received while sending, up to `receive_timeout` after the last packet. A
        packet counts as relayed, in both directions, when its echo came back.

        Designed to run as a fire-and-forget background task (see `AsyncLoop.add`).
        """
        failure_reason: MessageSendFailureReason | None = None
        rate = send_rate(burst_rate, session.mtu)
        total = packets_per_burst(burst_rate, burst_duration, session.mtu)
        message.batch_size = total
        receiver: asyncio.Task[int] | None = None
        sent = 0

        try:
            receiver = asyncio.create_task(
                session.receive(
                    message.packet_size,
                    total * message.packet_size,
                    timeout=burst_duration + receive_timeout,
                )
            )

            started_at = time.monotonic()
            attempted = 0
            while attempted < total:
                due = min(total, int((time.monotonic() - started_at) * rate) + 1)
                while attempted < due:
                    message.update_timestamp()
                    if session.send(message):
                        sent += 1
                    attempted += 1
                if attempted < total:
                    await asyncio.sleep(BURST_PACING_TICK_SECONDS)

            received_bytes = await receiver
            echoed = min(sent, received_bytes // message.packet_size)

            MESSAGES_SENT_SUCCESS.inc()
            MESSAGE_E2E_LATENCY.observe(time.time() - message.queued_at)
            return BurstResult(sent=sent, echoed=echoed)

        except asyncio.TimeoutError:
            failure_reason = MessageSendFailureReason.TIMEOUT
            raise
        except AttributeError as e:
            # Session socket is None (session closed)
            if "socket is None" in str(e).lower():
                failure_reason = MessageSendFailureReason.SESSION_CLOSED
            else:
                failure_reason = MessageSendFailureReason.UNKNOWN
            raise
        except OSError:
            # Socket errors (rare for UDP but can happen)
            failure_reason = MessageSendFailureReason.SOCKET_ERROR
            raise
        except Exception:
            failure_reason = MessageSendFailureReason.UNKNOWN
            raise
        finally:
            if receiver is not None and not receiver.done():
                receiver.cancel()
            if failure_reason:
                MESSAGES_SENT_FAILED.labels(reason=failure_reason.value).inc()
