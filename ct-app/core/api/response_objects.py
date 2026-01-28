import asyncio
import logging
import socket as socket_lib
import time
from dataclasses import fields
from typing import Any, Optional, Union

from api_lib.objects.response import (
    APIfield,
    APImetric,
    APIobject,
    JsonResponse,
    MetricResponse,
)
from prometheus_client import Gauge, Histogram

from ..components.balance import Balance
from ..components.messages.message_format import MessageFormat
from .channelstatus import ChannelStatus

MESSAGES_RTT = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["relayer"],
    buckets=[0.5, 0.75, 1, 2, 3, 4, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["relayer"])

logger = logging.getLogger(__name__)

# Socket I/O configuration
DEFAULT_RECEIVE_TIMEOUT_SECONDS = 2.0  # Default timeout for receiving data from UDP socket


def try_to_lower(value: Any):
    if isinstance(value, str):
        return value.lower()
    return value


@APIobject
class Addresses(JsonResponse):
    native: str


@APIobject
class Balances(JsonResponse):
    hopr: Balance
    native: Balance
    safe_native: Balance = APIfield("safeNative")
    safe_hopr: Balance = APIfield("safeHopr")


@APIobject
class Infos(JsonResponse):
    hopr_node_safe: str = APIfield("hoprNodeSafe")

    def post_init(self):
        self.hopr_node_safe = try_to_lower(self.hopr_node_safe)


@APIobject
class ConnectedPeer(JsonResponse):
    address: str
    multiaddr: str

    def post_init(self):
        self.address = try_to_lower(self.address)


@APIobject
class Channel(JsonResponse):
    balance: Balance
    id: str = APIfield("channelId")
    destination: str
    source: str
    status: ChannelStatus

    def post_init(self):
        self.destination = try_to_lower(self.destination)
        self.source = try_to_lower(self.source)


@APIobject
class OwnChannel(JsonResponse):
    id: str
    peer_address: str = APIfield("peerAddress")
    status: ChannelStatus
    balance: Balance


@APIobject
class TicketPrice(JsonResponse):
    value: Balance = APIfield("price")


@APIobject
class Configuration(JsonResponse):
    price: Balance = APIfield("hopr/protocol/outgoing_ticket_price")


@APIobject
class OpenedChannel(JsonResponse):
    channel_id: str = APIfield("channelId")
    receipt: str = APIfield("transactionReceipt", "")


@APIobject
class Metrics(MetricResponse):
    hopr_tickets_incoming_statistics: dict = APImetric(["statistic"])
    hopr_packets_count: dict = APImetric(["type"])


class Channels:
    def __init__(self, data: dict):
        self.all = [Channel(c) for c in data.get("all", [])]
        self.incoming = [OwnChannel(c) for c in data.get("incoming", [])]
        self.outgoing = [OwnChannel(c) for c in data.get("outgoing", [])]

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return str(self)


@APIobject
class Session(JsonResponse):
    """
    Represents an active UDP session for message relay to a peer.

    A Session encapsulates both the API-level session state and the local UDP socket
    connection used for sending/receiving messages. Sessions have a lifecycle managed
    by SessionMixin with a 60-second grace period before closure.

    Attributes:
        ip (str): IP address for socket connection (usually "127.0.0.1")
        port (int): UDP port assigned by the HOPR node API
        protocol (str): Protocol type (typically "udp")
        target (str): Peer address this session relays to
        mtu (int): Maximum transmission unit from HOPR protocol
        surb_size (int): Size of SURB (Single Use Reply Block) overhead
        socket (Optional[socket]): Local UDP socket, None if closed

    Properties:
        payload (int): Usable payload size = mtu - surb_size
        as_path (str): API path for this session
        as_dict (dict): Dictionary representation of session state

    Thread Safety:
        Socket operations are NOT thread-safe. However, this is safe in the current
        design because asyncio runs in a single thread and we avoid concurrent access
        through the snapshot pattern in maintain_sessions().

    Lifecycle:
        1. Created via NodeHelper.open_session() (API call)
        2. Socket created via create_socket()
        3. Used for send/receive operations
        4. Closed via close_socket() when peer unreachable or node stopping
        5. Removed from API via NodeHelper.close_session()
    """

    ip: str
    port: int
    protocol: str
    target: str
    mtu: int = APIfield("hoprMtu")
    surb_size: int = APIfield("surbLen")
    socket: Optional[socket_lib.socket] = None

    @property
    def payload(self):
        """
        Calculate usable payload size for messages.

        Returns:
            int: Maximum bytes available for message data (mtu - surb_size)
        """
        return self.mtu - self.surb_size

    @property
    def as_path(self):
        """
        Generate API path for this session.

        Returns:
            str: Path like "/session/udp/127.0.0.1/9001"
        """
        return f"/session/{self.protocol}/{self.ip}/{self.port}"

    @property
    def as_dict(self) -> dict:
        """
        Convert session to dictionary representation.

        Returns:
            dict: All session fields as strings
        """
        return {key: str(getattr(self, key)) for key in [f.name for f in fields(self)]}

    def create_socket(self) -> socket_lib.socket:
        """
        Create and configure UDP socket for this session.

        Creates a non-blocking UDP socket for use with asyncio event loop.
        The socket is set to non-blocking mode to work with loop.sock_recvfrom().

        Socket Lifecycle:
            - If a socket already exists, it is closed before creating a new one
            - This prevents resource leaks from multiple create_socket() calls
            - Safe to call multiple times (idempotent with cleanup)

        Returns:
            socket: Configured non-blocking UDP socket

        Example:
            >>> session.create_socket()  # Creates new socket
            >>> session.create_socket()  # Closes old socket, creates new one
            >>> session.close_socket()   # Closes and clears socket
        """
        # Close existing socket if present to prevent resource leak
        if self.socket is not None:
            self.close_socket()

        # Create new non-blocking UDP socket
        self.socket = socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_DGRAM)
        self.socket.setblocking(False)
        return self.socket

    def close_socket(self):
        """
        Close the UDP socket and clear the reference.

        Implements exception-safe socket closing with try/except/finally to ensure
        the socket reference is always cleared even if close() raises an exception.
        This prevents socket leaks and ensures clean shutdown.

        Exception Handling:
            - Logs socket.close() failures but continues
            - Always sets self.socket = None in finally block
            - Safe to call multiple times (idempotent)

        Thread Safety:
            Synchronous operation, no await statements. Safe to call from
            maintain_sessions() Phase 5 (atomic section).

        Example:
            >>> session.create_socket()
            >>> session.close_socket()  # Socket closed, self.socket = None
            >>> session.close_socket()  # No-op, safe to call again
        """
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                logger.exception(f"Failed to close socket on port {self.port}")
            finally:
                # Always clear socket reference, even if close failed
                self.socket = None

    def send(self, message: Union[MessageFormat, bytes]) -> int:
        """
        Send data to the peer via UDP socket.

        Sends a message and updates Prometheus metrics for monitoring. Supports both
        MessageFormat objects (with automatic serialization) and raw bytes.

        Args:
            message: Either a MessageFormat object or raw bytes to send

        Returns:
            int: Number of bytes sent (from socket.sendto())

        Metrics:
            - MESSAGE_SENDING_REQUEST: Incremented when send is called
            - MESSAGES_STATS: Incremented when message is successfully sent

        Raises:
            AttributeError: If socket is None (session closed)
            OSError: If socket send fails (rare for UDP)
            BlockingIOError: If socket buffer is full (rare, logged but not raised)

        Note:
            This is a synchronous operation using a non-blocking socket. UDP sends
            rarely block, but if they do, a BlockingIOError is caught and logged.
            For batch sends, use NodeHelper.send_batch_messages() which handles
            receive operations.
        """
        if self.socket is None:
            raise AttributeError(f"Socket is None for session on port {self.port}")

        if isinstance(message, MessageFormat):
            MESSAGE_SENDING_REQUEST.labels(message.relayer).inc()

        payload: bytes = message.bytes() if isinstance(message, MessageFormat) else message

        try:
            data = self.socket.sendto(payload, (self.ip, self.port))
        except BlockingIOError:
            # Rare case: socket buffer full on non-blocking socket
            logger.warning(
                f"Socket buffer full, send would block on port {self.port} "
                f"(payload_size={len(payload)} bytes)"
            )
            return 0

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.relayer).inc()

        return data

    async def receive(
        self, chunk_size: int, total_size: int, timeout: float = DEFAULT_RECEIVE_TIMEOUT_SECONDS
    ) -> int:
        """
        Receive data from the peer via UDP socket with timeout (non-blocking).

        Uses asyncio event loop integration via loop.sock_recvfrom() for truly
        non-blocking I/O. Continuously receives data until total_size is reached
        or timeout expires. Parses messages and updates Prometheus metrics.

        Args:
            chunk_size (int): Maximum bytes to receive per recvfrom() call (must be > 0)
            total_size (int): Total expected bytes to receive (if <= 0, returns 0)
            timeout (float): Maximum seconds to wait for data (default: 2)

        Returns:
            int: Total bytes received (may be less than total_size if timeout)

        Raises:
            ValueError: If chunk_size <= 0

        Behavior:
            - Non-blocking I/O via loop.sock_recvfrom()
            - Monotonic timeout tracking via asyncio.timeout (Python 3.11+)
            - Event loop efficiently wakes on socket readiness (no polling)
            - Handles ConnectionResetError gracefully
            - Parses MessageFormat from received data
            - Updates MESSAGES_STATS and MESSAGES_RTT metrics

        Exception Handling:
            - asyncio.TimeoutError: Returns partial data received
            - ConnectionResetError: Breaks loop, returns partial data
            - Decode/parse errors: Logged and skipped, doesn't fail

        Thread Safety:
            This is an async method that yields to the event loop. Safe because
            it doesn't modify shared state (only reads from socket and updates metrics).

        Example:
            >>> await session.receive(500, 5000, timeout=3.0)
            4500  # Received 4500 bytes before timeout
        """
        if not self.socket:
            return 0

        # Validate inputs
        if chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {chunk_size} for session on port {self.port}"
            )
        if total_size <= 0:
            return 0  # Nothing to receive

        loop = asyncio.get_running_loop()
        recv_data = bytearray()

        try:
            async with asyncio.timeout(timeout):
                while len(recv_data) < total_size:
                    to_read = min(chunk_size, total_size - len(recv_data))
                    if to_read <= 0:
                        break  # Safety check: avoid zero-length recv
                    data, _ = await loop.sock_recvfrom(self.socket, to_read)
                    if not data:
                        break
                    recv_data += data
        except ConnectionResetError:
            pass
        except asyncio.TimeoutError:
            pass

        # Use wall-clock time for RTT calculation (must match sender's timestamp)
        now_ms = int(time.time() * 1000)
        recv_size: int = len(recv_data)

        # Parse received messages and update metrics
        try:
            parts: list[str] = [item for item in recv_data.decode().split("\0") if item]
        except Exception:
            return recv_size

        for msg_str in parts:
            try:
                message = MessageFormat.parse(msg_str)
            except ValueError:
                continue

            rtt = (now_ms - message.timestamp) / 1000
            MESSAGES_STATS.labels("received", message.relayer).inc()
            MESSAGES_RTT.labels(message.relayer).observe(rtt)

        return recv_size


@APIobject
class SessionFailure(JsonResponse):
    status: str = APIfield("status")
    error: str = APIfield("error")
    destination: str = APIfield("destination", "")
    relayer: str = APIfield("relayer", "")
