import asyncio
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
        self.socket = socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_DGRAM)
        self.socket.settimeout(0.05)
        return self.socket

    def close_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None

    def send(self, message: Union[MessageFormat, bytes]) -> bytes:
        """
        Sends data to the peer.
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
