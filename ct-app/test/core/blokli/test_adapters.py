from core.blokli.adapters import (
    to_node_safe_link_from_account,
    to_safe_balance_snapshot,
)
from core.blokli.entries import BlokliAccount, BlokliHoprBalance


def test_to_node_safe_link_from_account_returns_none_when_safe_missing():
    account = BlokliAccount({"accountUpdated": {"chainKey": "0xnode", "safeAddress": None}})

    assert to_node_safe_link_from_account(account) is None


def test_to_node_safe_link_from_account_maps_fields():
    account = BlokliAccount({"accountUpdated": {"chainKey": "0xnode", "safeAddress": "0xsafe"}})

    link = to_node_safe_link_from_account(account)

    assert link is not None
    assert link.node_address == "0xnode"
    assert link.safe_address == "0xsafe"


def test_to_safe_balance_snapshot_returns_none_when_balance_missing():
    hopr_balance = BlokliHoprBalance({"hoprBalance": {"address": "0xsafe", "balance": None}})

    assert to_safe_balance_snapshot(hopr_balance) is None


def test_to_safe_balance_snapshot_maps_fields():
    hopr_balance = BlokliHoprBalance({"hoprBalance": {"address": "0xsafe", "balance": "12 wxHOPR"}})

    snapshot = to_safe_balance_snapshot(hopr_balance)

    assert snapshot is not None
    assert snapshot.safe_address == "0xsafe"
    assert snapshot.balance.as_str == "12 wxHOPR"
