from .base_classes import ExplicitParams


class ChannelParams(ExplicitParams):
    keys = {"min_balance": float,
            "funding_amount": float, "max_age_seconds": int}
