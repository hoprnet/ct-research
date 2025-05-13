from .base_classes import ExplicitParams


class PeerParams(ExplicitParams):
    keys = {
        "min_version": str,
        "sleep_mean_time": int,
        "sleep_std_time": int,
    }
