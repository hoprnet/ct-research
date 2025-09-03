import asyncio
import logging
import socket
from datetime import datetime
from typing import Optional, Union

from prometheus_client import Gauge, Histogram

from ..api.hoprd_api import HoprdAPI
from ..components.logs import configure_logging
from ..components.messages.message_format import MessageFormat
from ..components.node_helper import NodeHelper

MESSAGES_RTT = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["relayer"],
    buckets=[0.5, 0.75, 1, 2, 3, 4, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["relayer"])

configure_logging()
logger = logging.getLogger(__name__)


class SocketThroughNetwork:
    def __init__(
        self,
        api: HoprdAPI,
        destination: str,
        relayer: str,
        listen_host: Optional[str] = None,
        timeout: Optional[float] = 0.05,
    ):
        self.api = api
        self.destination = destination
        self.relayer = relayer
        self.listen_host = listen_host if listen_host else "127.0.0.1"
        self.timeout = timeout
        self.session = None
        self.socket = None

    async def __aenter__(self):
        self.session = await NodeHelper.open_session(
            self.api, self.destination, self.relayer, self.listen_host
        )

        if not self.session:
            return None

        try:
            self.socket = self.create_socket(self.timeout)
        except (socket.error, ValueError) as e:
            raise ValueError(f"Error while creating socket: {e}")

        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.session:
            await NodeHelper.close_session(self.api, self.session, self.relayer)
        else:
            return

        try:
            self.close_socket()
        except Exception as e:
            self.socket = None
            raise ValueError(f"Error closing socket: {e}") from e
        finally:
            self.socket = None

    def create_socket(self, timeout: Optional[float] = None) -> socket.socket:
        s: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
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
        data = self.socket.sendto(payload, (self.listen_host, self.session.port))

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
                recv_data += self.socket.recvfrom(chunk_size)[0]
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
                MESSAGES_RTT.labels(message.relayer).observe(rtt)

        return recv_size
