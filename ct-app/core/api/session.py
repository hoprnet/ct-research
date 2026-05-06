import asyncio
import logging
import socket as socket_lib
import time
from dataclasses import fields
from typing import Optional, Union

from api_lib.objects.response import APIfield, APIobject, JsonResponse
from prometheus_client import Gauge, Histogram

from ..types.message_format import MessageFormat

MESSAGES_RTT = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["relayer"],
    buckets=[0.5, 0.75, 1, 2, 3, 4, 5],
)
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "relayer"])
MESSAGE_SENDING_REQUEST = Gauge("ct_message_sending_request", "", ["relayer"])

logger = logging.getLogger(__name__)
DEFAULT_RECEIVE_TIMEOUT_SECONDS = 2.0


def _count_invalid_message_fragments(parts: list[str]) -> int:
    invalid_fragments = 0
    for msg_str in parts:
        try:
            message = MessageFormat.parse(msg_str)
        except ValueError:
            invalid_fragments += 1
            continue

        rtt = (int(time.time() * 1000) - message.timestamp) / 1000
        MESSAGES_STATS.labels("received", message.relayer).inc()
        MESSAGES_RTT.labels(message.relayer).observe(rtt)

    return invalid_fragments


@APIobject
class Session(JsonResponse):
    ip: str
    port: int
    protocol: str
    target: str
    mtu: int = APIfield("hoprMtu")
    surb_size: int = APIfield("surbLen")
    socket: Optional[socket_lib.socket] = None

    @property
    def payload(self):
        return self.mtu - self.surb_size

    @property
    def as_path(self):
        return f"/session/{self.protocol}/{self.ip}/{self.port}"

    @property
    def as_dict(self) -> dict:
        return {key: str(getattr(self, key)) for key in [f.name for f in fields(self)]}

    def create_socket(self) -> socket_lib.socket:
        if self.socket is not None:
            self.close_socket()

        self.socket = socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_DGRAM)
        self.socket.setblocking(False)
        return self.socket

    def close_socket(self):
        if self.socket:
            try:
                self.socket.close()
            except OSError as err:
                logger.warning("Failed to close socket on port %s: %s", self.port, err)
                self.socket = None
            else:
                self.socket = None

    def send(self, message: Union[MessageFormat, bytes]) -> int:
        if self.socket is None:
            raise AttributeError(f"Socket is None for session on port {self.port}")

        if isinstance(message, MessageFormat):
            MESSAGE_SENDING_REQUEST.labels(message.relayer).inc()

        payload: bytes = message.bytes() if isinstance(message, MessageFormat) else message

        try:
            data = self.socket.sendto(payload, (self.ip, self.port))
        except BlockingIOError:
            logger.warning(
                "Socket buffer full, send would block on port %s (payload_size=%s bytes)",
                self.port,
                len(payload),
            )
            return 0

        if isinstance(message, MessageFormat):
            MESSAGES_STATS.labels("sent", message.relayer).inc()

        return data

    async def receive(
        self, chunk_size: int, total_size: int, timeout: float = DEFAULT_RECEIVE_TIMEOUT_SECONDS
    ) -> int:
        if not self.socket:
            return 0
        if chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be positive, got {chunk_size} for session on port {self.port}"
            )
        if total_size <= 0:
            return 0

        loop = asyncio.get_running_loop()
        recv_data = bytearray()

        try:
            async with asyncio.timeout(timeout):
                while len(recv_data) < total_size:
                    to_read = min(chunk_size, total_size - len(recv_data))
                    if to_read <= 0:
                        break
                    data, _ = await loop.sock_recvfrom(self.socket, to_read)
                    if not data:
                        break
                    recv_data += data
        except ConnectionResetError as err:
            logger.warning(
                "Receive reset on port %s after %s bytes: %s",
                self.port,
                len(recv_data),
                err,
            )
        except asyncio.TimeoutError:
            logger.debug(
                "Receive timed out on port %s after %s/%s bytes",
                self.port,
                len(recv_data),
                total_size,
            )

        recv_size = len(recv_data)
        try:
            parts: list[str] = [item for item in recv_data.decode().split("\0") if item]
        except UnicodeDecodeError as err:
            logger.warning(
                "Failed to decode %s bytes received on port %s: %s",
                recv_size,
                self.port,
                err,
            )
            return recv_size

        invalid_fragments = _count_invalid_message_fragments(parts)
        if invalid_fragments:
            logger.debug(
                "Skipped %s invalid message fragments on port %s",
                invalid_fragments,
                self.port,
            )

        return recv_size
