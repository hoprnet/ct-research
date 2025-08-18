import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge, Histogram

from core.api.protocol import Protocol
from core.api.response_objects import Session
from core.components.logs import configure_logging
from core.components.messages.message_format import MessageFormat

MESSAGES_DELAYS = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["sender", "relayer"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "sender", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["sender", "relayer"])

configure_logging()
logger = logging.getLogger(__name__)


class SessionToSocket:
    def __init__(self, session: Session, connect_address: str, timeout: Optional[float] = 0.05):
        self.session = session
        self.connect_address = connect_address

        try:
            self.socket = self.create_socket(timeout)
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.socket:
                self.socket.close()
        except Exception as e:
            self.socket = None
            raise ValueError(f"Error closing socket: {e}") from e
        finally:
            self.socket = None

    @property
    def port(self) -> int:
        """
        Returns the session port number.
        """
        return self.session.port

    @property
    def address(self):
        """
        Returns the socket address tuple.
        """

        return (self.connect_address, self.session.port)

    def create_socket(self, timeout: Optional[float] = None) -> socket.socket:
        if self.session.protocol == Protocol.UDP:
            s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif self.session.protocol == Protocol.TCP:
            s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.connect(self.address)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        s.settimeout(timeout)

        return s

    async def send(self, message: MessageFormat) -> bytes:
        """
        Sends data to the peer.
        """
        MESSAGE_SENDING_REQUEST.labels(message.sender, message.relayer).inc()

        payload: bytes = message.bytes()

        match self.session.protocol:
            case Protocol.UDP:
                self.socket.sendto(payload, self.address)
            case Protocol.TCP:
                self.socket.send(payload)

        MESSAGES_STATS.labels("sent", message.sender, message.relayer).inc()
        return payload

    async def receive(self, chunk_size: int, timeout: float = 1) -> tuple[list[str], int]:
        """
        Receives data from the peer. In case off multiple message in the same packet, which should
        not happen, they are already split and returned as a list.
        """
        recv_data = b""

        start_time = datetime.now().timestamp()

        while True:
            if (datetime.now().timestamp() - start_time) >= timeout:
                break

            try:
                if self.session.protocol == Protocol.UDP:
                    data: bytes = self.socket.recvfrom(chunk_size)[0]
                if self.session.protocol == Protocol.TCP:
                    data: bytes = self.socket.recv(chunk_size)
                recv_data += data
            except socket.timeout:
                await asyncio.sleep(0.02)
                pass
            except ConnectionResetError:
                break

        now = int(datetime.now().timestamp() * 1000)
        recv_size: int = len(recv_data)

        recv_data: list[str] = [
            item for item in recv_data.decode().split(b"\0".decode()) if len(item) > 0
        ]

        for data in recv_data:
            try:
                message = MessageFormat.parse(data)
            except ValueError as e:
                logger.error(f"Failed to parse message: {e}")
                continue

            rtt = (now - message.timestamp) / 1000
            MESSAGES_STATS.labels("received", message.sender, message.relayer).inc()
            MESSAGES_DELAYS.labels(message.sender, message.relayer).observe(rtt)

        return recv_data, recv_size
