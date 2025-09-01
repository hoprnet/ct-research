import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional, Union

from prometheus_client import Gauge, Histogram

from ..api.protocol import Protocol
from ..api.response_objects import Session
from ..components.logs import configure_logging
from ..components.messages.message_format import MessageFormat

MESSAGES_RTT = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["sender", "relayer"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["relayer"])

configure_logging()
logger = logging.getLogger(__name__)


class SessionToSocket:
    def __init__(
        self,
        session: Session,
        connect_address: Optional[str] = None,
        timeout: Optional[float] = 0.05,
    ):
        self.session = session
        self.connect_address = connect_address if connect_address else "127.0.0.1"

        try:
            self.socket = self.create_socket(timeout)
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close_socket()
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

    def close_socket(self):
        if self.socket:
            self.socket.close()

    def send(self, message: Union[MessageFormat, bytes]) -> bytes:
        """
        Sends data to the peer.
        """
        if isinstance(message, MessageFormat):
            MESSAGE_SENDING_REQUEST.labels(message.relayer).inc()

        payload: bytes = message.bytes() if isinstance(message, MessageFormat) else message

        match self.session.protocol:
            case Protocol.UDP:
                data = self.socket.sendto(payload, self.address)
            case Protocol.TCP:
                data = self.socket.send(payload)

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.relayer).inc()

        return data

    async def receive(self, chunk_size: int, total_size: int, timeout: float = 2) -> int:
        """
        Receives data from the peer. In case off multiple message in the same packet, which should
        not happen, they are already split and returned as a list.
        """
        recv_data = b""

        start_time = datetime.now().timestamp()

        while len(recv_data) < total_size:
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

        try:
            recv_data: list[str] = [
                item for item in recv_data.decode().split(b"\0".decode()) if len(item) > 0
            ]
        except Exception:
            logger.error("Failed to decode received data")
        else:
            for data in recv_data:
                try:
                    message = MessageFormat.parse(data)
                except ValueError as e:
                    logger.error(f"Failed to parse message: {e}")
                    continue

                rtt = (now - message.timestamp) / 1000
                MESSAGES_STATS.labels("received", message.relayer).inc()
                MESSAGES_RTT.labels(message.sender, message.relayer).observe(rtt)

        return recv_size
