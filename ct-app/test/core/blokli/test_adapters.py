import pytest

from core.api.channelstatus import ChannelStatus
from core.blokli.adapters import to_channel, to_node_ip
from core.blokli.entries import BlokliChannelGraphEntry, BlokliNodeAddressEntry


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


def _node_entry(multi_addresses: list[str], chain_key: str = "0xAbC") -> BlokliNodeAddressEntry:
    return BlokliNodeAddressEntry(
        {"accountUpdated": {"chainKey": chain_key, "multiAddresses": multi_addresses}}
    )


@pytest.mark.parametrize(
    "announced, expected_host",
    [
        ("/ip4/1.2.3.4/udp/4001/quic", "1.2.3.4"),
        ("/ip6/2001:db8::1/tcp/9091", "2001:db8::1"),
        ("/dns4/node.example/tcp/9091", "node.example"),
        ("5.6.7.8", "5.6.7.8"),
    ],
)
def test_to_node_ip_extracts_host(announced: str, expected_host: str):
    address, host = to_node_ip(_node_entry([announced]))

    assert address == "0xabc"
    assert host == expected_host


def test_to_node_ip_skips_unusable_and_takes_first_usable():
    address, host = to_node_ip(_node_entry(["/p2p/12D3Koo", "/dns4/node.example/tcp/9091"]))

    assert address == "0xabc"
    assert host == "node.example"


@pytest.mark.parametrize("multi_addresses", [[], [""], ["/ip4"], ["/p2p/12D3Koo"]])
def test_to_node_ip_returns_none_for_unusable_address(multi_addresses: list[str]):
    assert to_node_ip(_node_entry(multi_addresses)) is None
