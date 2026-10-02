from typing import Optional

from ..api.channelstatus import ChannelStatus
from ..api.response_objects import Channel
from .entries import BlokliChannelGraphEntry

# Blokli reports channel statuses in upper case, hoprd (and ChannelStatus) in PascalCase.
_BLOKLI_CHANNEL_STATUS = {
    "OPEN": ChannelStatus.Open,
    "PENDINGTOCLOSE": ChannelStatus.PendingToClose,
    "CLOSED": ChannelStatus.Closed,
}


def to_channel(entry: BlokliChannelGraphEntry) -> Optional[Channel]:
    if None in (entry.channel_id, entry.source, entry.destination, entry.balance, entry.status):
        return None
    status = _BLOKLI_CHANNEL_STATUS.get(entry.status.upper(), ChannelStatus.Unknown)
    return Channel(
        {
            "balance": entry.balance.as_str,
            "destination": entry.destination,
            "source": entry.source,
            "status": status.value,
        }
    )
