from typing import Optional

from ..api.channelstatus import ChannelStatus
from ..api.response_objects import Channel
from .entries import BlokliAccount, BlokliChannelGraphEntry, BlokliHoprBalance
from ..types.network_models import NodeSafeLink, SafeBalanceSnapshot

# Blokli reports channel statuses in upper case, hoprd (and ChannelStatus) in PascalCase.
_BLOKLI_CHANNEL_STATUS = {
    "OPEN": ChannelStatus.Open,
    "PENDINGTOCLOSE": ChannelStatus.PendingToClose,
    "CLOSED": ChannelStatus.Closed,
}


def to_node_safe_link_from_account(account: BlokliAccount) -> Optional[NodeSafeLink]:
    # A missing safe address means the node was unlinked; keep it so the link gets removed.
    if account.node_address is None:
        return None
    return NodeSafeLink(node_address=account.node_address, safe_address=account.safe_address)


def to_safe_balance_snapshot(balance: BlokliHoprBalance) -> Optional[SafeBalanceSnapshot]:
    if not balance.is_valid or balance.address is None or balance.balance is None:
        return None
    return SafeBalanceSnapshot(safe_address=balance.address, balance=balance.balance)


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
