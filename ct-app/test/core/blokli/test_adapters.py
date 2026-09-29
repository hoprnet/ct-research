import pytest

from core.api.channelstatus import ChannelStatus
from core.blokli.adapters import (
    to_channel,
    to_node_safe_link_from_account,
    to_safe_balance_snapshot,
)
from core.blokli.entries import (
    BlokliAccount,
    BlokliChannelGraphEntry,
    BlokliHoprBalance,
    BlokliRedemptionStats,
)


def test_to_node_safe_link_from_account_keeps_unlink_when_safe_missing():
    account = BlokliAccount({"accountUpdated": {"chainKey": "0xnode", "safeAddress": None}})

    link = to_node_safe_link_from_account(account)

    assert link is not None
    assert link.node_address == "0xnode"
    assert link.safe_address is None


def test_to_node_safe_link_from_account_returns_none_when_node_missing():
    account = BlokliAccount({"accountUpdated": {"chainKey": None, "safeAddress": "0xsafe"}})

    assert to_node_safe_link_from_account(account) is None


def test_to_node_safe_link_from_account_maps_fields():
    account = BlokliAccount({"accountUpdated": {"chainKey": "0xnode", "safeAddress": "0xsafe"}})

    link = to_node_safe_link_from_account(account)

    assert link is not None
    assert link.node_address == "0xnode"
    assert link.safe_address == "0xsafe"


def test_blokli_account_lowercases_addresses():
    account = BlokliAccount(
        {"accountUpdated": {"chainKey": "0xAbCdEf", "safeAddress": "0xSaFeAbC"}}
    )

    assert account.node_address == "0xabcdef"
    assert account.safe_address == "0xsafeabc"


def test_to_safe_balance_snapshot_returns_none_when_balance_missing():
    hopr_balance = BlokliHoprBalance(
        {"hoprBalance": {"__typename": "HoprBalance", "address": "0xsafe", "balance": None}}
    )

    assert to_safe_balance_snapshot(hopr_balance) is None


def test_to_safe_balance_snapshot_maps_fields():
    hopr_balance = BlokliHoprBalance(
        {"hoprBalance": {"__typename": "HoprBalance", "address": "0xSaFe", "balance": "12 wxHOPR"}}
    )

    snapshot = to_safe_balance_snapshot(hopr_balance)

    assert snapshot is not None
    assert snapshot.safe_address == "0xsafe"
    assert snapshot.balance.as_str == "12 wxHOPR"


def test_to_safe_balance_snapshot_returns_none_for_error_variant():
    hopr_balance = BlokliHoprBalance(
        {
            "hoprBalance": {
                "__typename": "QueryFailedError",
                "code": "QUERY_FAILED",
                "message": "database unavailable",
            }
        }
    )

    assert not hopr_balance.is_valid
    assert hopr_balance.error == "database unavailable"
    assert to_safe_balance_snapshot(hopr_balance) is None


def test_to_safe_balance_snapshot_returns_none_for_failed_request():
    # A failed request (e.g. Blokli answering 503 while indexing) is converted from `{}`.
    assert to_safe_balance_snapshot(BlokliHoprBalance({})) is None


def test_redemption_stats_validity():
    valid = BlokliRedemptionStats(
        {
            "ticketRedemptionStats": {
                "__typename": "RedeemedStats",
                "redeemedAmount": "3 wxHOPR",
                "redemptionCount": 2,
            }
        }
    )
    error = BlokliRedemptionStats(
        {
            "ticketRedemptionStats": {
                "__typename": "MissingFilterError",
                "code": "MISSING_FILTER",
                "message": "no filter",
            }
        }
    )

    assert valid.is_valid
    assert valid.redeemed_amount.as_str == "3 wxHOPR"
    assert not error.is_valid
    assert error.error == "no filter"
    assert not BlokliRedemptionStats({}).is_valid


def _graph_entry(status: str) -> BlokliChannelGraphEntry:
    return BlokliChannelGraphEntry(
        {
            "openedChannelGraphUpdated": {
                "channel": {
                    "concreteChannelId": "0xAbC",
                    "balance": "2.5 wxHOPR",
                    "status": status,
                },
                "source": {"chainKey": "0xSoUrCe"},
                "destination": {"chainKey": "0xDeSt"},
            }
        }
    )


@pytest.mark.parametrize(
    "status, expected",
    [
        ("OPEN", ChannelStatus.Open),
        ("PENDINGTOCLOSE", ChannelStatus.PendingToClose),
        ("CLOSED", ChannelStatus.Closed),
        ("SOMETHING_NEW", ChannelStatus.Unknown),
    ],
)
def test_to_channel_maps_blokli_graph_entry(status: str, expected: ChannelStatus):
    entry = _graph_entry(status)

    channel = to_channel(entry)

    assert entry.channel_id == "0xabc"
    assert channel is not None
    assert channel.source == "0xsource"
    assert channel.destination == "0xdest"
    assert channel.balance.as_str == "2.5 wxHOPR"
    assert channel.status == expected


def test_to_channel_returns_none_for_incomplete_entry():
    assert to_channel(BlokliChannelGraphEntry({})) is None
