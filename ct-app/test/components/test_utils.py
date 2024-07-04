import datetime
import inspect
from test.components.utils import handle_envvars

import pytest
from core.components.utils import Utils
from core.model.address import Address
from core.model.peer import Peer
from core.model.subgraph_entry import SubgraphEntry
from core.model.topology_entry import TopologyEntry
from hoprd_sdk.models import ChannelInfoResponse


@pytest.fixture
def channel_topology():
    return [
        ChannelInfoResponse(
            f"{1*1e18:.0f}",
            1,
            "channel_1",
            5,
            "dst_addr_1",
            "dst_1",
            "src_addr_1",
            "src_1",
            "Open",
            0,
        ),
        ChannelInfoResponse(
            f"{2*1e18:.0f}",
            1,
            "channel_2",
            5,
            "dst_addr_2",
            "dst_2",
            "src_addr_1",
            "src_1",
            "Open",
            0,
        ),
        ChannelInfoResponse(
            f"{3*1e18:.0f}",
            1,
            "channel_3",
            5,
            "dst_addr_3",
            "dst_3",
            "src_addr_1",
            "src_1",
            "Closed",
            0,
        ),
        ChannelInfoResponse(
            f"{4*1e18:.0f}",
            1,
            "channel_4",
            5,
            "dst_addr_1",
            "dst_1",
            "src_addr_2",
            "src_2",
            "Open",
            0,
        ),
        ChannelInfoResponse(
            f"{1*1e18:.0f}",
            1,
            "channel_5",
            5,
            "dst_addr_2",
            "dst_2",
            "src_addr_2",
            "src_2",
            "Open",
            0,
        ),
    ]


def test_nodeAddresses():
    with handle_envvars(
        node_address_1="address_1",
        node_address_2="address_2",
        node_key_1="address_1_key",
        node_key_2="address_2_key",
    ):
        addresses, keys = Utils.nodesAddresses("NODE_ADDRESS_", "NODE_KEY_")
        assert addresses == ["address_1", "address_2"]
        assert keys == ["address_1_key", "address_2_key"]


def test_httpPOST():
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_mergeDataSources():
    topology_list = [
        TopologyEntry(None, None, 1),
        TopologyEntry("peer_id_2", "address_2", 2),
        TopologyEntry("peer_id_3", "address_3", 3),
        TopologyEntry("peer_id_4", "address_4", 4),
    ]
    peers_list = [
        Peer("peer_id_1", "address_1", "1.0.0"),
        Peer("peer_id_2", "address_2", "1.1.0"),
        Peer("peer_id_3", "address_3", "1.0.2"),
    ]
    subgraph_list = [
        SubgraphEntry("address_1", "10", "safe_address_1", "1"),
        SubgraphEntry("address_2", "10", "safe_address_2", "2"),
        SubgraphEntry("address_3", None, "safe_address_3", "3"),
    ]

    merged = await Utils.mergeDataSources(topology_list, peers_list, subgraph_list)

    assert len(merged) == 3


def test_allowManyNodePerSafe():
    peer_1 = Peer("id_1", "address_1", "v1.0.0")
    peer_2 = Peer("id_2", "address_2", "v1.1.0")
    peer_3 = Peer("id_3", "address_3", "v1.0.2")
    peer_4 = Peer("id_4", "address_4", "v1.0.0")

    peer_1.safe_address = "safe_address_1"
    peer_2.safe_address = "safe_address_2"
    peer_3.safe_address = "safe_address_3"
    peer_4.safe_address = "safe_address_2"

    source_data = [peer_1, peer_2, peer_3, peer_4]

    assert all([peer.safe_address_count == 1 for peer in source_data])

    Utils.allowManyNodePerSafe(source_data)

    assert peer_1.safe_address_count == 1
    assert peer_2.safe_address_count == 2
    assert peer_3.safe_address_count == 1


def test_exclude():
    source_data = [
        Peer("id_1", "address_1", "v1.0.0"),
        Peer("id_2", "address_2", "v1.1.0"),
        Peer("id_3", "address_3", "v1.0.2"),
        Peer("id_4", "address_4", "v1.0.0"),
        Peer("id_5", "address_5", "v1.1.1"),
    ]
    blacklist = [Address("id_2", "address_2"), Address("id_4", "address_4")]

    excluded = Utils.exclude(source_data, blacklist)

    assert len(source_data) == 3
    assert len(excluded) == 2
    for item in excluded:
        assert item.address in blacklist


def test_nextEpoch():
    timestamp = Utils.nextEpoch(1000)
    now = datetime.datetime.now()

    assert now < timestamp
    assert (timestamp - now).total_seconds() < 1000


def test_nextDelayInSeconds():
    delay = Utils.nextDelayInSeconds(1000)
    assert delay < 1000

    delay = Utils.nextDelayInSeconds(0)
    assert delay == 1

    delay = Utils.nextDelayInSeconds(1)
    assert delay == 1


@pytest.mark.asyncio
async def test_aggregatePeerBalanceInChannels(channel_topology):
    results = await Utils.aggregatePeerBalanceInChannels(channel_topology)

    assert len(results) == 2
    assert results["src_1"]["channels_balance"] == 3
    assert results["src_2"]["channels_balance"] == 5
