from dataclasses import dataclass

from ..types.balance import Balance
from .base_classes import Duration, ExplicitParams


@dataclass(init=False)
class ChannelParams(ExplicitParams):
    min_balance: Balance
    funding_amount: Balance
    max_age: Duration
