from dataclasses import dataclass, field
from datetime import datetime

from .balance import Balance


@dataclass
class NetworkState:
    node_to_safe: dict[str, str] = field(default_factory=dict)
    safe_balances: dict[str, Balance] = field(default_factory=dict)
    reachable_nodes: set[str] = field(default_factory=set)
    outgoing_channel_balances: dict[str, Balance] = field(default_factory=dict)
    last_links_refresh_at: datetime | None = None
    last_balances_refresh_at: datetime | None = None
