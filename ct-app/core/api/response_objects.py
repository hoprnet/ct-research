import asyncio
import logging
import socket as socket_lib
from dataclasses import fields
from datetime import datetime
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

        Creates a non-blocking UDP socket with 50ms timeout. The short timeout
        allows the asyncio event loop to remain responsive while waiting for data.

        Returns:
            socket: Configured UDP socket

        Note:
            Should only be called once per session. Multiple calls will replace
            the existing socket without closing it (resource leak).
        """
        self.socket: socket_lib.socket = socket_lib.socket(
            socket_lib.AF_INET, socket_lib.SOCK_DGRAM
        )
        self.socket.settimeout(0.05)
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
            except Exception as e:
                logger.error("Failed to close socket", {"error": str(e), "port": self.port})
            finally:
                # Always clear socket reference, even if close failed
                self.socket = None

    def send(self, message: Union[MessageFormat, bytes]) -> bytes:
        """
        Send data to the peer via UDP socket.

        Sends a message and updates Prometheus metrics for monitoring. Supports both
        MessageFormat objects (with automatic serialization) and raw bytes.

        Args:
            message: Either a MessageFormat object or raw bytes to send

        Returns:
            bytes: Number of bytes sent (from socket.sendto())

        Metrics:
            - MESSAGE_SENDING_REQUEST: Incremented when send is called
            - MESSAGES_STATS: Incremented when message is successfully sent

        Raises:
            AttributeError: If socket is None (session closed)
            OSError: If socket send fails

        Note:
            This is a synchronous operation. For batch sends, use
            NodeHelper.send_batch_messages() which handles receive operations.
        """
        if isinstance(message, MessageFormat):
            MESSAGE_SENDING_REQUEST.labels(message.relayer).inc()

        payload: bytes = message.bytes() if isinstance(message, MessageFormat) else message
        data = self.socket.sendto(payload, (self.ip, self.port))

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.relayer).inc()

        return data

    async def receive(self, chunk_size: int, total_size: int, timeout: float = 2) -> int:
        """
        Receive data from the peer via UDP socket with timeout.

        Continuously receives data until total_size is reached or timeout expires.
        Handles multiple messages in a single packet, parses them, and updates
        Prometheus metrics for round-trip time (RTT) tracking.

        Args:
            chunk_size (int): Maximum bytes to receive per recvfrom() call
            total_size (int): Total expected bytes to receive
            timeout (float): Maximum seconds to wait for data (default: 2)

        Returns:
            int: Total bytes received (may be less than total_size if timeout)

        Behavior:
            - Loops until total_size received or timeout expires
            - Yields to event loop every 20ms during socket timeout
            - Handles ConnectionResetError gracefully
            - Parses MessageFormat from received data
            - Updates MESSAGES_STATS and MESSAGES_RTT metrics

        Exception Handling:
            - socket.timeout: Yields to event loop, continues receiving
            - ConnectionResetError: Breaks loop, returns partial data
            - Decode/parse errors: Logged and skipped, doesn't fail

        Thread Safety:
            This is an async method that yields to the event loop. Safe because
            it doesn't modify shared state (only reads from socket and updates metrics).

        Example:
            >>> await session.receive(500, 5000, timeout=3.0)
            4500  # Received 4500 bytes before timeout
        """
        recv_data = b""

        start_time = datetime.now().timestamp()

        while len(recv_data) < total_size:
            if (datetime.now().timestamp() - start_time) >= timeout:
                break

            try:
                recv_data += self.socket.recvfrom(chunk_size)[0]
            except socket_lib.timeout:
                await asyncio.sleep(0.02)
                pass
            except ConnectionResetError:
                break

        now = int(datetime.now().timestamp() * 1000)
        recv_size: int = len(recv_data)

        try:
            recv_data: list[str] = [
                item for item in recv_data.decode().split(b"\0".decode()) if len(item) > 0
            ]
        except Exception:
            pass
        else:
            for data in recv_data:
                try:
                    message = MessageFormat.parse(data)
                except ValueError as _e:
                    continue

                rtt = (now - message.timestamp) / 1000
                MESSAGES_STATS.labels("received", message.relayer).inc()
                MESSAGES_RTT.labels(message.relayer).observe(rtt)

        return recv_size


@APIobject
class SessionFailure(JsonResponse):
    status: str = APIfield("status")
    error: str = APIfield("error")
