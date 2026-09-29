from dataclasses import dataclass

from ..api.response_objects import Channel
from .balance import Balance


@dataclass(frozen=True)
class NodeSafeLink:
    node_address: str
    safe_address: str | None


@dataclass(frozen=True)
class SafeBalanceSnapshot:
    safe_address: str
    balance: Balance


@dataclass(frozen=True)
class ChannelGraphUpdate:
    channel_id: str
    channel: Channel
