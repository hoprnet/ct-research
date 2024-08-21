import pytest
from core.components import Utils
from core.model import Address, Peer
from core.model.subgraph import AllocationEntry, NodeEntry, SafeEntry, TopologyEntry
from hoprd_sdk.models import ChannelInfoResponse

from .utils import handle_envvars


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
        TopologyEntry("peer_id_1", "address_1", 1),
        TopologyEntry("peer_id_2", "address_2", 2),
        TopologyEntry(None, None, 3),
        TopologyEntry("peer_id_4", "address_4", 4),
    ]
    peers_list = [
        Peer("peer_id_1", "address_1", "1.0.0"),
        Peer("peer_id_2", "address_2", "1.1.0"),
        Peer("peer_id_3", "address_3", "1.0.2"),
    ]
    nodes_list = [
        NodeEntry("address_1", SafeEntry("safe_address_1", "10", "1", ["owner_1"])),
        NodeEntry(
            "address_2", SafeEntry("safe_address_2", "10", "2", ["owner_1", "owner_2"])
        ),
        NodeEntry("address_3", SafeEntry("safe_address_3", None, "3", ["owner_3"])),
    ]
    allocation_list = [
        AllocationEntry("owner_1", "0", f"{100*1e18:.0f}"),
        AllocationEntry("owner_2", "0", f"{250*1e18:.0f}"),
    ]

    allocation_list[0].linked_safes = ["safe_address_1", "safe_address_2"]
    allocation_list[1].linked_safes = ["safe_address_2"]

    merged: list[Peer] = await Utils.mergeDataSources(
        topology_list, peers_list, nodes_list, allocation_list
    )

    assert len(merged) == 3
    assert len([p for p in merged if p.safe is not None]) == 2
    assert merged[0].safe.additional_balance == allocation_list[0].allocatedAmount / 2
    assert (
        merged[1].safe.additional_balance
        == allocation_list[0].allocatedAmount / 2 + allocation_list[1].allocatedAmount
    )


def test_associateAllocationsAndSafes():
    allocations = [
        AllocationEntry("owner_1", "0", f"{100*1e18:.0f}"),
        AllocationEntry("owner_2", "0", f"{250*1e18:.0f}"),
    ]
    nodes = [
        NodeEntry("address_1", SafeEntry("safe_address_1", "10", "1", ["owner_1"])),
        NodeEntry(
            "address_2", SafeEntry("safe_address_2", "10", "2", ["owner_1", "owner_2"])
        ),
        NodeEntry("address_3", SafeEntry("safe_address_3", None, "3", ["owner_3"])),
    ]

    Utils.associateAllocationsAndSafes(allocations, nodes)

    assert allocations[0].linked_safes == ["safe_address_1", "safe_address_2"]
    assert allocations[1].linked_safes == ["safe_address_2"]


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


@pytest.mark.asyncio
async def test_balanceInChannels(channel_topology):
    results = await Utils.balanceInChannels(channel_topology)

    assert len(results) == 2
    assert results["src_1"]["channels_balance"] == 3
    assert results["src_2"]["channels_balance"] == 5
