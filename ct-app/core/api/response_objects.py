from dataclasses import fields
from typing import Any

from api_lib.objects.response import (
    APIfield,
    APImetric,
    APIobject,
    JsonResponse,
    MetricResponse,
)

from ..components.balance import Balance
from .channelstatus import ChannelStatus
from .protocol import Protocol


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
    protocol: Protocol
    target: str
    mtu: int
    surb_size: int = APIfield("surbLen")

    @property
    def payload(self):
        return self.mtu - self.surb_size

    @property
    def as_path(self):
        return f"/session/{self.protocol.value}/{self.ip}/{self.port}"

    @property
    def as_dict(self) -> dict:
        return {key: str(getattr(self, key)) for key in [f.name for f in fields(self)]}


@APIobject
class SessionFailure(JsonResponse):
    status: str = APIfield("status")
    error: str = APIfield("error")
