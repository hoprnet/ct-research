from typing import Optional

from ..api.channelstatus import ChannelStatus
from ..api.response_objects import Channel
from .entries import BlokliChannelGraphEntry, BlokliNodeAddressEntry

# Blokli reports channel statuses in upper case, hoprd (and ChannelStatus) in PascalCase.
_BLOKLI_CHANNEL_STATUS = {
    "OPEN": ChannelStatus.Open,
    "PENDINGTOCLOSE": ChannelStatus.PendingToClose,
    "CLOSED": ChannelStatus.Closed,
}


def _host_from_multiaddr(value: str) -> Optional[str]:
    """
    Extract the host from a single announced multiaddress. A node may announce either an IP
    (`/ip4/1.2.3.4/udp/4001/...`, `/ip6/.../...`) or a DNS name (`/dns4/host/...`, `/dns6/...`,
    `/dnsaddr/...`); both are returned as the grouping key. A bare IP/host (no leading `/`) is
    returned unchanged.
    """
    if not value:
        return None
    if not value.startswith("/"):
        return value

    parts = [part for part in value.split("/") if part]
    for key in ("ip4", "ip6", "dns", "dns4", "dns6", "dnsaddr"):
        if key in parts:
            index = parts.index(key)
            if index + 1 < len(parts):
                return parts[index + 1]
    return None


def to_node_ip(entry: BlokliNodeAddressEntry) -> Optional[tuple[str, str]]:
    """
    Map an account entry to `(address, host)`, where host is the IP or DNS name from the node's
    announced multiaddress. Returns None when the node has no usable announced address.
    """
    if entry.chain_key is None or not entry.multi_addresses:
        return None
    for multiaddr in entry.multi_addresses:
        host = _host_from_multiaddr(multiaddr)
        if host is not None:
            return entry.chain_key, host
    return None


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
