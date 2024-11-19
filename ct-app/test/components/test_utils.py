import pytest
from core.components import Utils
from core.components.api_types import Channel
from core.model import Address, Peer
from core.model.subgraph import entries

from .utils import handle_envvars


@pytest.fixture
def channel_topology():
    return [
        Channel(
            {
                "balance": f"{1*1e18:.0f}",
                "channelId": "channel_1",
                "destinationAddress": "dst_addr_1",
                "destinationPeerId": "dst_1",
                "sourceAddress": "src_addr_1",
                "sourcePeerId": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": f"{2*1e18:.0f}",
                "channelId": "channel_2",
                "destinationAddress": "dst_addr_2",
                "destinationPeerId": "dst_2",
                "sourceAddress": "src_addr_1",
                "sourcePeerId": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": f"{3*1e18:.0f}",
                "channelId": "channel_3",
                "destinationAddress": "dst_addr_3",
                "destinationPeerId": "dst_3",
                "sourceAddress": "src_addr_1",
                "sourcePeerId": "src_1",
                "status": "Closed",
            }
        ),
        Channel(
            {
                "balance": f"{4*1e18:.0f}",
                "channelId": "channel_4",
                "destinationAddress": "dst_addr_1",
                "destinationPeerId": "dst_1",
                "sourceAddress": "src_addr_2",
                "sourcePeerId": "src_2",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": f"{1*1e18:.0f}",
                "channelId": "channel_5",
                "destinationAddress": "dst_addr_2",
                "destinationPeerId": "dst_2",
                "sourceAddress": "src_addr_2",
                "sourcePeerId": "src_2",
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
        entries.Topology("peer_id_1", "address_1", 1),
        entries.Topology("peer_id_2", "address_2", 2),
        entries.Topology(None, None, 3),
        entries.Topology("peer_id_4", "address_4", 4),
    ]
    peers_list = [
        Peer("peer_id_1", "address_1", "1.0.0"),
        Peer("peer_id_2", "address_2", "1.1.0"),
        Peer("peer_id_3", "address_3", "1.0.2"),
    ]
    nodes_list = [
        entries.Node(
            "address_1", entries.Safe("safe_address_1", "10", "1", ["owner_1"])
        ),
        entries.Node(
            "address_2",
            entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        entries.Node(
            "address_3", entries.Safe("safe_address_3", None, "3", ["owner_3"])
        ),
    ]
    allocation_list = [
        entries.Allocation("owner_1", "0", f"{100*1e18:.0f}"),
        entries.Allocation("owner_2", "0", f"{250*1e18:.0f}"),
    ]

    allocation_list[0].linked_safes = ["safe_address_1", "safe_address_2"]
    allocation_list[1].linked_safes = ["safe_address_2"]

    await Utils.mergeDataSources(
        topology_list, peers_list, nodes_list, allocation_list, {}
    )

    assert len(peers_list) == 3
    assert len([p for p in peers_list if p.safe is not None]) == 3
    assert (
        peers_list[0].safe.additional_balance == allocation_list[0].allocated_amount / 2
    )
    assert (
        peers_list[1].safe.additional_balance
        == allocation_list[0].allocated_amount / 2 + allocation_list[1].allocated_amount
    )


def test_associateEntitiesToNodes_with_allocations():
    allocations = [
        entries.Allocation("owner_1", "0", f"{100*1e18:.0f}"),
        entries.Allocation("owner_2", "0", f"{250*1e18:.0f}"),
    ]
    nodes = [
        entries.Node(
            "address_1", entries.Safe("safe_address_1", "10", "1", ["owner_1"])
        ),
        entries.Node(
            "address_2",
            entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        entries.Node(
            "address_3", entries.Safe("safe_address_3", None, "3", ["owner_3"])
        ),
    ]

    Utils.associateEntitiesToNodes(allocations, nodes)

    assert allocations[0].linked_safes == {"safe_address_1", "safe_address_2"}
    assert allocations[1].linked_safes == {"safe_address_2"}


def test_associateEntitiesToNodes_with_eoa_balances():
    balances = [
        entries.Balance("owner_1", f"{100*1e18:.0f}"),
        entries.Balance("owner_2", f"{250*1e18:.0f}"),
    ]
    nodes = [
        entries.Node(
            "address_1", entries.Safe("safe_address_1", "10", "1", ["owner_1"])
        ),
        entries.Node(
            "address_2",
            entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        entries.Node(
            "address_3", entries.Safe("safe_address_3", None, "3", ["owner_3"])
        ),
    ]

    Utils.associateEntitiesToNodes(balances, nodes)

    assert balances[0].linked_safes == {"safe_address_1", "safe_address_2"}
    assert balances[1].linked_safes == {"safe_address_2"}


def test_allowManyNodePerSafe():
    peer_1 = Peer("id_1", "address_1", "v1.0.0")
    peer_2 = Peer("id_2", "address_2", "v1.1.0")
    peer_3 = Peer("id_3", "address_3", "v1.0.2")
    peer_4 = Peer("id_4", "address_4", "v1.0.0")

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
