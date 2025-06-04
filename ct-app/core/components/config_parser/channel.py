from core.components.balance import Balance

from .base_classes import ExplicitParams


class ChannelParams(ExplicitParams):
    keys = {"min_balance": Balance, "funding_amount": Balance, "max_age_seconds": int}
