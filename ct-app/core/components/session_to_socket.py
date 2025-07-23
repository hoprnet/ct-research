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


configure_logging()
logger = logging.getLogger(__name__)


class SessionToSocket:
    def __init__(self, session: Session, connect_address: str, timeout: Optional[float] = 0.05):
        self.session = session
        self.connect_address = connect_address

        try:
            self.socket, self.conn = self.create_socket(timeout)
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

    def create_socket(self, timeout: Optional[float] = None):
        if self.session.protocol == Protocol.UDP:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            conn = None
        elif self.session.protocol == Protocol.TCP:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn = s.connect(self.address)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        s.settimeout(timeout)

        return s, conn

    async def send(self, message: MessageFormat, factor: int = 1) -> bytes:
        """
        Sends data to the peer.
        """
        payload: bytes = message.bytes()

        if self.session.protocol == Protocol.UDP:
            self.socket.sendto(payload, self.address)
        elif self.session.protocol == Protocol.TCP:
            self.socket.sendall(payload)

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.sender, message.relayer).inc(
                len(payload) / message.packet_size
            )
        return payload

    async def receive(self, chunk_size: int, timeout: float = 5) -> tuple[list[str], int]:
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
                    data, _ = self.socket.recvfrom(chunk_size)
                if self.session.protocol == Protocol.TCP:
                    data = self.socket.recv(chunk_size)
                recv_data += data
            except socket.timeout:
                await asyncio.sleep(0.1)
                pass
            except ConnectionResetError:
                logger.error("Connection reset by peer while receiving data")
                break

        now = int(datetime.now().timestamp() * 1000)
        recv_size: int = len(recv_data)
        recv_data: list[str] = [
            item for item in recv_data.decode().split(b"\0".decode()) if len(item) > 0
        ]

        for data in recv_data:
            try:
                message: MessageFormat = MessageFormat.parse(data)
            except ValueError as e:
                logger.error(f"Failed to parse message: {e}")
                continue

            rtt = (now - message.timestamp) / 1000
            MESSAGES_STATS.labels("received", message.sender, message.relayer).inc(
                message.multiplier
            )
            MESSAGES_DELAYS.labels(message.sender, message.relayer).observe(rtt)

        return recv_data, recv_size
