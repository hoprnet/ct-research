import socket
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge, Histogram

from core.api.protocol import Protocol
from core.api.response_objects import Session
from core.components.messages.message_format import MessageFormat

BUF_SIZE = 8192

MESSAGES_DELAYS = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["sender", "relayer"],
    buckets=[0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "sender", "relayer"])


class SessionToSocket:
    def __init__(
        self, session: Session, connect_address: str, timeout: Optional[int] = 0.05
    ):
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

    def create_socket(self, timeout: Optional[int]):
        if self.session.protocol == Protocol.UDP:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, BUF_SIZE)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUF_SIZE)

        if timeout is not None:
            s.settimeout(timeout)

        conn = None

        return s, conn

    def send(self, data: bytes) -> int:
        """
        Sends data to the peer.
        """
        if self.session.protocol == Protocol.UDP:
            return self.socket.sendto(data, self.address)
        else:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

    def receive(self, size: int) -> tuple[Optional[str], int, Optional[int]]:
        """
        Receives data from the peer. In case off multiple message in the same packet, which should
        not happen, they are already split and returned as a list.
        """
        if self.session.protocol != Protocol.UDP:
            raise ValueError(f"Invalid protocol: {self.session.protocol}")

        try:
            data, _ = self.socket.recvfrom(size)
            now = int(datetime.now().timestamp() * 1000)
            return data.rstrip(b"\0").decode(), len(data), now
        except socket.timeout:
            return None, 0, None

    async def send_and_receive(self, message: MessageFormat) -> float:
        # TODO: maybe set the timestamp here ?

        sent_size = self.send(message.bytes())
        recv_message, recv_size, timestamp = self.receive(sent_size)

        if recv_message is None:
            return 0

        try:
            message = MessageFormat.parse(recv_message)
        except ValueError:
            return 0

        rtt = (timestamp - message.timestamp) / 1000

        # convert to number of messages instead of bytes
        sent_count = sent_size / 476
        recv_count = recv_size / 476

        MESSAGES_STATS.labels("sent", message.sender, message.relayer).inc(sent_count)
        MESSAGES_STATS.labels("relayed", message.sender, message.relayer).inc(
            recv_count
        )
        MESSAGES_DELAYS.labels(message.sender, message.relayer).observe(rtt)

        return recv_size / sent_size
