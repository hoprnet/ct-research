from .base_classes import ExplicitParams


class SessionsParams(ExplicitParams):
    keys = {
        "aggregated_packets": int,
        "batch_size": int,
    }
