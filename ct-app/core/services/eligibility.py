from collections.abc import Iterable

from ..api.response_objects import Channel
from ..types.balance import Balance


def qualifying_outgoing_channels(
    channels: Iterable[Channel], min_channel_balance: Balance
) -> dict[str, int]:
    """
    Count, per source node, the open outgoing channels holding at least `min_channel_balance`.
    Channels below that balance don't count.
    """
    counts: dict[str, int] = {}
    for channel in channels:
        if not channel.status.is_open:
            continue
        if channel.balance < min_channel_balance:
            continue
        counts[channel.source] = counts.get(channel.source, 0) + 1
    return counts


def is_eligible(
    address: str,
    reachable: bool,
    qualifying_channels: int,
    min_outgoing_channels: int,
    ct_nodes: Iterable[str],
    exclusion_list: Iterable[str],
) -> bool:
    """
    A relayer is eligible when this CT node can reach it, it has at least
    `min_outgoing_channels` qualifying outgoing channels, and it is neither a CT node nor
    excluded. Stake, safe balance and location play no part.
    """
    if not reachable:
        return False
    if address in ct_nodes or address in exclusion_list:
        return False
    return qualifying_channels >= min_outgoing_channels
