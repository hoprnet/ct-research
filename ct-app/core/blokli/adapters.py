from typing import Optional

from .entries import BlokliAccount, BlokliHoprBalance
from ..types.network_models import NodeSafeLink, SafeBalanceSnapshot


def to_node_safe_link_from_account(account: BlokliAccount) -> Optional[NodeSafeLink]:
    if account.node_address is None or account.safe_address is None:
        return None
    return NodeSafeLink(node_address=account.node_address, safe_address=account.safe_address)


def to_safe_balance_snapshot(balance: BlokliHoprBalance) -> Optional[SafeBalanceSnapshot]:
    if balance.address is None or balance.balance is None:
        return None
    return SafeBalanceSnapshot(safe_address=balance.address, balance=balance.balance)
