from dataclasses import dataclass

from ..types.balance import Balance
from .base_classes import Duration, ExplicitParams


@dataclass(init=False, repr=False)
class IncentiveParams(ExplicitParams):
    # Eligibility: open outgoing channels holding at least `min_channel_balance`.
    min_outgoing_channels: int
    min_channel_balance: Balance

    # Burst shape. `burst_rate` is in Mbit/s (10^6 bit/s).
    burst_rate: float
    burst_duration: Duration

    # Target average time between two bursts reaching the same relayer, across all CT nodes.
    target_relayer_interval: Duration
    # Maximum bursts one CT node runs at the same time. 0 = no limit.
    max_concurrent_bursts_per_ct: int
    # Number of CT nodes in the deployment (C). Sets each CT node's round length.
    ct_node_count: int
