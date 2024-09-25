import inspect

import pytest
from core.model import Peer

from .conftest import Core


@pytest.mark.asyncio
async def test_connected_peers(core: Core, peers: list[Peer]):
    assert len(await core.all_peers.get()) == 0

    # drop manually some peers (all in but #3)
    peers_list = list(peers)
    await core.nodes[0].peers.set(set(peers_list[:3]))
    await core.nodes[1].peers.set(set(peers_list[4:]))
    await core.nodes[2].peers.set(set(peers_list[::2]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers) - 1
    assert (
        sum([(await peer.yearly_message_count.get()) is not None for peer in all_peers])
        == 4
    )

    # drop manually all but #0 and #1
    for node in core.nodes:
        await node.peers.set(set(peers_list[:2]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers) - 1
    assert (
        sum([(await peer.yearly_message_count.get()) is not None for peer in all_peers])
        == 2
    )
    # last peer appear
    await core.nodes[0].peers.update(set([peers_list[3]]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert (
        sum([(await peer.yearly_message_count.get()) is not None for peer in all_peers])
        == 3
    )

    # peer reappear
    await core.nodes[0].peers.update(set([peers_list[-1]]))

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert (
        sum([(await peer.yearly_message_count.get()) is not None for peer in all_peers])
        == 4
    )

    # all disappear
    for node in core.nodes:
        await node.peers.set(set())

    await core.connected_peers()
    all_peers = await core.all_peers.get()

    assert len(all_peers) == len(peers)
    assert (
        sum([(await peer.yearly_message_count.get()) is not None for peer in all_peers])
        == 0
    )


@pytest.mark.asyncio
async def test_get_topology_data(core: Core, peers: list[Peer]):
    await core.topology()

    assert len(await core.topology_list.get()) == len(peers)


@pytest.mark.asyncio
async def test_apply_economic_model(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_get_fundings(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")
