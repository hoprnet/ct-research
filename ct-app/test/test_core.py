import pytest

from core.components import Peer

from .conftest import Core


@pytest.mark.asyncio
async def test_connected_peers(core: Core, peers: list[Peer]):
    assert len(await core.all_peers.get()) == 0

    # drop manually some peers (all in but #3)
    peers_list = list(peers)
    core.nodes[0].peers = set(peers_list[:3])
    core.nodes[1].peers = set(peers_list[4:])
    core.nodes[2].peers = set(peers_list[::2])

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers) - 1
    assert sum([peer.yearly_message_count is not None for peer in all_peers]) == 4

    # drop manually all but #0 and #1
    for node in core.nodes:
        node.peers = set(peers_list[:2])

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers) - 1
    assert sum([peer.yearly_message_count is not None for peer in all_peers]) == 2
    # last peer appear
    core.nodes[0].peers.update(set([peers_list[3]]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert sum([peer.yearly_message_count is not None for peer in all_peers]) == 3

    # peer reappear
    core.nodes[0].peers.update(set([peers_list[-1]]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert sum([peer.yearly_message_count is not None for peer in all_peers]) == 4

    # all disappear
    for node in core.nodes:
        node.peers = set()

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert sum([peer.yearly_message_count is not None for peer in all_peers]) == 0


@pytest.mark.asyncio
async def test_get_topology_data(core: Core, peers: list[Peer]):
    for n in core.nodes:
        await n.retrieve_channels()

    await core.topology()

    assert len(core.topology_data) == len(peers)
