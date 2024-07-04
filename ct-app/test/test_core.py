import inspect
import os

import pytest
from core.model.address import Address
from core.model.peer import Peer
from core.model.subgraph_type import SubgraphType

from .conftest import Core


def test__safe_subgraph_url(core: Core):
    assert "query-id-safes" in core._safe_subgraph_url(SubgraphType.DEFAULT)
    assert core._safe_subgraph_url(SubgraphType.BACKUP) == "safes_backup_url"
    assert core._safe_subgraph_url("random") is None


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
    await core.nodes[0].peers.set(set(list(await core.nodes[0].peers.get())[:3]))
    await core.nodes[1].peers.set(set(list(await core.nodes[1].peers.get())[2:]))
    await core.nodes[2].peers.set(set(list(await core.nodes[2].peers.get())[::2]))

    await core.aggregate_peers()

    assert len(await core.all_peers.get()) == len(peers)


@pytest.mark.asyncio
async def test_get_subgraph_data(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_get_topology_data(core: Core, peers: list[Peer]):
    await core.connected.set(True)
    await core.get_topology_data()

    assert len(await core.topology_list.get()) == len(peers)


@pytest.mark.asyncio
async def test_apply_economic_model(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_get_fundings(core: Core):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")
