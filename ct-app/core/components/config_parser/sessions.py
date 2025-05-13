from .base_classes import ExplicitParams


class SessionsParams(ExplicitParams):
    keys = {
        "packet_size": int,
        "aggregated_packets": int,
        "batch_size": int,
    }
