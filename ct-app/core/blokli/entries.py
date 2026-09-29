from typing import Any, Optional

from api_lib.objects.response import APIfield, APIobject, JsonResponse

from core.types.balance import Balance


def _lower(value: Any):
    return value.lower() if isinstance(value, str) else value


@APIobject
class BlokliHoprBalance(JsonResponse):
    typename: Optional[str] = APIfield(path="hoprBalance/__typename")
    address: str = APIfield(path="hoprBalance/address")
    balance: Balance = APIfield(path="hoprBalance/balance")
    error: Optional[str] = APIfield(path="hoprBalance/message")

    def post_init(self):
        self.address = _lower(self.address)

    @property
    def is_valid(self) -> bool:
        # Any other typename is one of the union's error variants; a missing one means the
        # request itself failed (e.g. Blokli answering 503 while indexing).
        return self.typename == "HoprBalance"


@APIobject
class BlokliRedemptionStats(JsonResponse):
    typename: Optional[str] = APIfield(path="ticketRedemptionStats/__typename")
    redeemed_amount: Optional[Balance] = APIfield(path="ticketRedemptionStats/redeemedAmount")
    error: Optional[str] = APIfield(path="ticketRedemptionStats/message")

    @property
    def is_valid(self) -> bool:
        return self.typename == "RedeemedStats" and self.redeemed_amount is not None


@APIobject
class BlokliAccount(JsonResponse):
    node_address: str = APIfield(path="accountUpdated/chainKey")
    safe_address: Optional[str] = APIfield(path="accountUpdated/safeAddress")

    def post_init(self):
        self.node_address = _lower(self.node_address)
        self.safe_address = _lower(self.safe_address)


@APIobject
class BlokliTicketParameters(JsonResponse):
    min_ticket_winning_probability: float = APIfield(
        path="ticketParametersUpdated/minTicketWinningProbability"
    )
    ticket_price: Balance = APIfield(path="ticketParametersUpdated/ticketPrice")


@APIobject
class BlokliChannelGraphEntry(JsonResponse):
    channel_id: str = APIfield(path="openedChannelGraphUpdated/channel/concreteChannelId")
    balance: Balance = APIfield(path="openedChannelGraphUpdated/channel/balance")
    # OPEN, PENDINGTOCLOSE or CLOSED. CLOSED means the channel must be dropped.
    status: str = APIfield(path="openedChannelGraphUpdated/channel/status")
    source: str = APIfield(path="openedChannelGraphUpdated/source/chainKey")
    destination: str = APIfield(path="openedChannelGraphUpdated/destination/chainKey")

    def post_init(self):
        self.channel_id = _lower(self.channel_id)
        self.source = _lower(self.source)
        self.destination = _lower(self.destination)
