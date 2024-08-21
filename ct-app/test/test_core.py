import inspect
import pytest
from core.model import Peer
from core.model.subgraph import SubgraphType

from .conftest import Core


def test_safe_subgraph_url(core: Core):
    core.subgraph_type = SubgraphType.DEFAULT
    print(f"{core.safe_sg_url=}")
    assert "query-id-safes" in core.safe_sg_url

    core.subgraph_type = SubgraphType.BACKUP
    assert "safes_backup_url" in core.safe_sg_url

    core.subgraph_type = SubgraphType.NONE
    assert core.safe_sg_url is None


@pytest.mark.asyncio
async def test_core_healthcheck(core: Core):
    await core.healthcheck()

    assert await core.connected.get()


@pytest.mark.asyncio
async def test_check_subgraph_urls(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_aggregate_peers(core: Core, peers: list[Peer]):
    assert len(await core.all_peers.get()) == 0

    # drop manually some peers from nodes
    await core.nodes[0].peers.set(set(peers[:3]))
    await core.nodes[1].peers.set(set(peers[2:]))
    await core.nodes[2].peers.set(set(peers[::2]))

    await core.connected_peers()

    assert len(await core.all_peers.get()) == len(peers)

    for peer in await core.all_peers.get():
        peer.running = False


@pytest.mark.asyncio
async def test_get_subgraph_data(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_get_topology_data(core: Core, peers: list[Peer]):
    await core.connected.set(True)
    await core.topology()

    assert len(await core.topology_list.get()) == len(peers)


@pytest.mark.asyncio
async def test_apply_economic_model(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_get_fundings(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")
