from typing import Optional

from api_lib.objects.response import APIfield, APIobject, JsonResponse

from core.types.balance import Balance


@APIobject
class BlokliHoprBalance(JsonResponse):
    address: str = APIfield(path="hoprBalance/address")
    balance: Balance = APIfield(path="hoprBalance/balance")


@APIobject
class BlokliRedemptionStats(JsonResponse):
    node_address: Optional[str] = APIfield(path="redeemedStats/nodeAddress")
    safe_address: Optional[str] = APIfield(path="redeemedStats/safeAddress")
    redeemed_amount: Optional[Balance] = APIfield(path="redeemedStats/redeemedAmount")


@APIobject
class BlokliAccount(JsonResponse):
    node_address: str = APIfield(path="accountUpdated/chainKey")
    safe_address: Optional[str] = APIfield(path="accountUpdated/safeAddress")


@APIobject
class BlokliTicketParameters(JsonResponse):
    min_ticket_winning_probability: float = APIfield(
        path="ticketParametersUpdated/minTicketWinningProbability"
    )
    ticket_price: Balance = APIfield(path="ticketParametersUpdated/ticketPrice")
