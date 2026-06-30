from dataclasses import dataclass

from ..types.balance import Balance
from .base_classes import Duration, ExplicitParams


@dataclass(init=False, repr=False)
class ChannelParams(ExplicitParams):
    min_balance: Balance
    funding_amount: Balance
    funding_cooldown: Duration
    max_age: Duration
