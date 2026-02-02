from dataclasses import dataclass

from ..balance import Balance
from .base_classes import Duration, ExplicitParams


@dataclass(init=False)
class ChannelParams(ExplicitParams):
    min_balance: Balance
    funding_amount: Balance
    max_age_seconds: Duration
