from dataclasses import dataclass

from .balance import Balance


@dataclass(frozen=True)
class NodeSafeLink:
    node_address: str
    safe_address: str


@dataclass(frozen=True)
class SafeBalanceSnapshot:
    safe_address: str
    balance: Balance
