import pytest

from core.api.channelstatus import ChannelStatus
from core.blokli.adapters import to_channel
from core.blokli.entries import BlokliChannelGraphEntry


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
