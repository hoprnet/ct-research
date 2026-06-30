import logging
from typing import Any

from api_lib.objects.response import (
    APIfield,
    APIobject,
    JsonResponse,
)

from ..types.balance import Balance
from .channelstatus import ChannelStatus
from .session import Session

logger = logging.getLogger(__name__)
__all__ = [
    "Addresses",
    "Balances",
    "ConnectedPeer",
    "Channel",
    "TicketPrice",
    "OpenedChannel",
    "Channels",
    "Session",
    "SessionFailure",
]


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
class ConnectedPeer(JsonResponse):
    address: str

    def post_init(self):
        self.address = try_to_lower(self.address)


@APIobject
class Channel(JsonResponse):
    balance: Balance
    destination: str
    source: str
    status: ChannelStatus

    # TODO: maybe remove the conversion
    def post_init(self):
        self.destination = try_to_lower(self.destination)
        self.source = try_to_lower(self.source)


@APIobject
class TicketPrice(JsonResponse):
    value: Balance = APIfield("price")


@APIobject
class OpenedChannel(JsonResponse):
    channel_id: str = APIfield("channelId")


@APIobject
class Channels(JsonResponse):
    all: list[Channel]
    incoming: list[Channel]
    outgoing: list[Channel]


@APIobject
class SessionFailure(JsonResponse):
    status: str
    error: str
    destination: str = APIfield(default="")
    relayer: str = APIfield(default="")
