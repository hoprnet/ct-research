import pytest

from core.api.response_objects import Channel
from core.components import Peer, Utils
from core.components.balance import Balance
from core.rpc import entries as rpc_entries
from core.subgraph import entries as sg_entries

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
        sg_entries.Topology("address_1", Balance("1 wxHOPR")),
        sg_entries.Topology("address_2", Balance("2 wxHOPR")),
        sg_entries.Topology(None, Balance("3 wxHOPR")),
        sg_entries.Topology("address_4", Balance("4 wxHOPR")),
    ]
    peers_list = [
        Peer("address_1", "1.0.0"),
        Peer("address_2", "1.1.0"),
        Peer("address_3", "1.0.2"),
    ]
    nodes_list = [
        sg_entries.Node("address_1", sg_entries.Safe("safe_address_1", "10", "1", ["owner_1"])),
        sg_entries.Node(
            "address_2",
            sg_entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        sg_entries.Node("address_3", sg_entries.Safe("safe_address_3", None, "3", ["owner_3"])),
    ]
    allocation_list = [
        rpc_entries.Allocation(
            "owner_1", "schedule", Balance("100 wxHOPR"), Balance.zero("wxHOPR")
        ),
        rpc_entries.Allocation(
            "owner_2", "schedule", Balance("250 wxHOPR"), Balance.zero("wxHOPR")
        ),
    ]

    allocation_list[0].linked_safes = ["safe_address_1", "safe_address_2"]
    allocation_list[1].linked_safes = ["safe_address_2"]

    await Utils.mergeDataSources(topology_list, peers_list, nodes_list, allocation_list, {})

    assert len(peers_list) == 3
    assert len([p for p in peers_list if p.safe is not None]) == 3
    assert peers_list[0].safe.additional_balance == allocation_list[0].amount / 2
    assert (
        peers_list[1].safe.additional_balance
        == allocation_list[0].amount / 2 + allocation_list[1].amount
    )


def test_associateEntitiesToNodes_with_allocations():
    allocations = [
        rpc_entries.Allocation(
            "owner_1", "schedule", Balance("100 wxHOPR"), Balance.zero("wxHOPR")
        ),
        rpc_entries.Allocation(
            "owner_2", "schedule", Balance("250 wxHOPR"), Balance.zero("wxHOPR")
        ),
    ]
    nodes = [
        sg_entries.Node("address_1", sg_entries.Safe("safe_address_1", "10", "1", ["owner_1"])),
        sg_entries.Node(
            "address_2",
            sg_entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        sg_entries.Node("address_3", sg_entries.Safe("safe_address_3", None, "3", ["owner_3"])),
    ]

    Utils.associateEntitiesToNodes(allocations, nodes)

    assert allocations[0].linked_safes == {"safe_address_1", "safe_address_2"}
    assert allocations[1].linked_safes == {"safe_address_2"}


def test_associateEntitiesToNodes_with_balances():
    balances = [
        rpc_entries.ExternalBalance("owner_1", Balance("100 wxHOPR")),
        rpc_entries.ExternalBalance("owner_2", Balance("250 wxHOPR")),
    ]
    nodes = [
        sg_entries.Node("address_1", sg_entries.Safe("safe_address_1", "10", "1", ["owner_1"])),
        sg_entries.Node(
            "address_2",
            sg_entries.Safe("safe_address_2", "10", "2", ["owner_1", "owner_2"]),
        ),
        sg_entries.Node("address_3", sg_entries.Safe("safe_address_3", None, "3", ["owner_3"])),
    ]

    Utils.associateEntitiesToNodes(balances, nodes)

    assert balances[0].linked_safes == {"safe_address_1", "safe_address_2"}
    assert balances[1].linked_safes == {"safe_address_2"}


def test_allowManyNodePerSafe():
    peer_1 = Peer("address_1", "v1.0.0")
    peer_2 = Peer("address_2", "v1.1.0")
    peer_3 = Peer("address_3", "v1.0.2")
    peer_4 = Peer("address_4", "v1.0.0")

    peer_1.safe = sg_entries.Safe("safe_address_1", "10", "1", [])
    peer_2.safe = sg_entries.Safe("safe_address_2", "10", "1", [])
    peer_3.safe = sg_entries.Safe("safe_address_3", "10", "1", [])
    peer_4.safe = sg_entries.Safe("safe_address_2", "10", "1", [])

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
