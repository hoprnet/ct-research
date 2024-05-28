import pytest
from core.model.address import Address
from core.model.peer import Peer
from core.model.subgraph_type import SubgraphType

from .conftest import Core


def test__safe_subgraph_url(core: Core):
    assert core._safe_subgraph_url(SubgraphType.DEFAULT) == "safes default url"
    assert core._safe_subgraph_url(SubgraphType.BACKUP) == "safes backup url"
    assert core._safe_subgraph_url("random") is None


@pytest.mark.asyncio
async def test__retrieve_address(core: Core, addresses: list[dict]):
    await core._retrieve_address()

    assert core.address == Address(addresses[-1]["hopr"], addresses[-1]["native"])


@pytest.mark.asyncio
async def test_healthcheck(core: Core):
    await core.healthcheck()

    assert await core.connected.get()


@pytest.mark.asyncio
async def test_check_subgraph_urls(core: Core):
    pytest.skip("Not implemented")


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
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_get_topology_data(core: Core, peers: list[Peer]):
    await core.get_topology_data()

    assert len(await core.topology_list.get()) == len(peers)


@pytest.mark.asyncio
async def test_apply_economic_model(core: Core):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_prepare_distribution(core: Core):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_get_fundings(core: Core):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_multiple_attempts_sending_stops_by_reward(core: Core, peers: list[Peer]):
    max_iter = 20
    rewards, iter = await core.multiple_attempts_sending(peers[:-1], max_iter)

    assert iter < max_iter
    assert len(rewards) == len(peers) - 1
    assert all([reward["remaining"] <= 0 for reward in rewards.values()])
    assert all([reward["issued"] >= reward["expected"] for reward in rewards.values()])


@pytest.mark.asyncio
async def test_multiple_attempts_sending_stops_by_max_iter(
    core: Core, peers: list[Peer]
):
    max_iter = 2
    await core.get_ticket_price()
    rewards, iter = await core.multiple_attempts_sending(peers[:-1], max_iter)

    assert iter == max_iter
    assert len(rewards) == len(peers) - 1
    assert all([reward["remaining"] >= 0 for reward in rewards.values()])
