import pytest

from core.api.response_objects import Channel
from core.components import Peer, Utils
from core.components.balance import Balance
from core.subgraph import entries

from .utils import handle_envvars


@pytest.fixture
def channel_topology():
    return [
        Channel(
            {
                "balance": "1 wxHOPR",
                "channelId": "channel_1",
                "destination": "dst_1",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "2 wxHOPR",
                "channelId": "channel_2",
                "destination": "dst_2",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "3 wxHOPR",
                "channelId": "channel_3",
                "destination": "dst_3",
                "source": "src_1",
                "status": "Closed",
            }
        ),
        Channel(
            {
                "balance": "4 wxHOPR",
                "channelId": "channel_4",
                "destination": "dst_1",
                "source": "src_2",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "1 wxHOPR",
                "channelId": "channel_5",
                "destination": "dst_2",
                "source": "src_2",
                "status": "Open",
            }
        ),
    ]


def test_nodesCredentials():
    with handle_envvars(
        node_address_1="address_1",
        node_address_2="address_2",
        node_key_1="address_1_key",
        node_key_2="address_2_key",
    ):
        addresses, keys = Utils.nodesCredentials("NODE_ADDRESS", "NODE_KEY")
        assert addresses == ["address_1", "address_2"]
        assert keys == ["address_1_key", "address_2_key"]


@pytest.mark.asyncio
async def test_mergeDataSources():

    topology_list = [
        entries.Topology("address_1", Balance("1 wxHOPR")),
        entries.Topology("address_2", Balance("2 wxHOPR")),
        entries.Topology(None, Balance("3 wxHOPR")),
        entries.Topology("address_4", Balance("4 wxHOPR")),
    ]
    peers_list = [
        Peer("address_1"),
        Peer("address_2"),
        Peer("address_3"),
    ]
    nodes_list = [
        entries.Node("address_1", entries.Safe("safe_address_1", "10", "1", ["owner_1"])),
        entries.Node(
            "address_2",
            entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        entries.Node("address_3", entries.Safe("safe_address_3", None, "3", ["owner_3"])),
    ]

    await Utils.mergeDataSources(topology_list, peers_list, nodes_list)

    assert len(peers_list) == 3
    assert len([p for p in peers_list if p.safe is not None]) == 3


def test_allowManyNodePerSafe():
    peer_1 = Peer("address_1")
    peer_2 = Peer("address_2")
    peer_3 = Peer("address_3")
    peer_4 = Peer("address_4")

    peer_1.safe = entries.Safe("safe_address_1", "10", "1", [])
    peer_2.safe = entries.Safe("safe_address_2", "10", "1", [])
    peer_3.safe = entries.Safe("safe_address_3", "10", "1", [])
    peer_4.safe = entries.Safe("safe_address_2", "10", "1", [])

    source_data = [peer_1, peer_2, peer_3, peer_4]

    assert all([peer.safe_address_count == 1 for peer in source_data])

    Utils.allowManyNodePerSafe(source_data)

    assert peer_1.safe_address_count == 1
    assert peer_2.safe_address_count == 2
    assert peer_3.safe_address_count == 1


@pytest.mark.asyncio
async def test_balanceInChannels(channel_topology):
    results = await Utils.balanceInChannels(channel_topology)

    assert len(results) == 2
    assert results["src_1"].value == 3
    assert results["src_2"].value == 5
