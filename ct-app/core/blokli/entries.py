from typing import Any

from api_lib.objects.response import APIfield, APIobject, JsonResponse

from core.types.balance import Balance


def _lower(value: Any):
    return value.lower() if isinstance(value, str) else value


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
