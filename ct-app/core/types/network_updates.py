from dataclasses import dataclass

from .balance import Balance


@dataclass(frozen=True)
class LinkUpdate:
    node_address: str
    safe_address: str


@dataclass(frozen=True)
class BalanceUpdate:
    safe_address: str
    balance: Balance


@dataclass(frozen=True)
class RedeemedUpdate:
    node_address: str
    safe_address: str
    peer_address: str
    redeemed_amount: Balance | None
