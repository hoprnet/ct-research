from random import randint
from test.decorators_patches import patches

import pytest
from core.components.parameters import Parameters
from core.model.address import Address
from core.model.economic_model import (
    BudgetParameters,
    EconomicModel,
    Equation,
    Equations,
)
from core.model.economic_model import Parameters as EMParameters
from core.model.peer import Peer
from core.model.subgraph_type import SubgraphType
from database import Utils as DBUtils
from hoprd_sdk.models import ChannelTopology, InlineResponse2006
from pytest_mock import MockerFixture

for p in patches:
    p.start()

# needs to be imported after the patches are applied
from core.core import Core  # noqa: E402
from core.node import Node  # noqa: E402


@pytest.fixture
def economic_model() -> EconomicModel:
    equations = Equations(
        Equation("a * x", "l <= x <= c"),
        Equation("a * c + (x - c) ** (1 / b)", "x > c"),
    )
    parameters = EMParameters(1, 1, 3, 0)
    budget = BudgetParameters(100, 15, 0.25, 2, 0.01, 1)
    return EconomicModel(equations, parameters, budget)


@pytest.fixture
def peers(economic_model: EconomicModel) -> list[Peer]:
    peers = [
        Peer("id_0", "address_0", "2.0.0"),
        Peer("id_1", "address_1", "1.7.0"),
        Peer("id_2", "address_2", "1.0.3"),
        Peer("id_3", "address_3", "1.0.0-rc.3"),
        Peer("id_4", "address_4", "1.0.0"),
    ]
    for peer in peers:
        peer.economic_model = economic_model
        peer.reward_probability = 0.02
        peer.safe_balance = randint(100, 200)
        peer.channel_balance = randint(10, 50)

    return peers


@pytest.fixture
def address() -> list[dict]:
    return [
        {"hopr": "id_0", "native": "address_0"},
        {"hopr": "id_1", "native": "address_1"},
        {"hopr": "id_2", "native": "address_2"},
        {"hopr": "id_3", "native": "address_3"},
        {"hopr": "id_4", "native": "address_4"},
    ]


@pytest.fixture
def nodes() -> list[Node]:
    return [
        Node("localhost:9000", "random_key"),
        Node("localhost:9001", "random_key"),
        Node("localhost:9002", "random_key"),
        Node("localhost:9003", "random_key"),
        Node("localhost:9004", "random_key"),
    ]


@pytest.fixture
def channels(peers: list[Peer]) -> InlineResponse2006:
    channels = list[ChannelTopology]()
    index = 0

    for src in peers:
        for dest in peers:
            if src.address == dest.address:
                continue

            channels.append(
                ChannelTopology(
                    f"channel_{index}",
                    src.address.id,
                    dest.address.id,
                    src.address.address,
                    dest.address.address,
                    f"{1*1e18:.0f}",
                    "Open",
                    "",
                    "",
                    "",
                )
            )
            index += 1

    return InlineResponse2006(all=channels)


@pytest.fixture
async def core(
    mocker: MockerFixture,
    nodes: list[Node],
    peers: list[Peer],
    address: list[dict],
    channels: InlineResponse2006,
    economic_model: EconomicModel,
) -> Core:
    core = Core()
    core.nodes = nodes

    mocker.patch.object(DBUtils, "peerIDToInt", return_value=0)

    for idx, node in enumerate(core.nodes):
        mocker.patch.object(node.peers, "get", return_value=peers)
        mocker.patch.object(node.api, "get_address", return_value=address[idx])
        mocker.patch.object(node.api, "all_channels", return_value=channels)
        mocker.patch.object(node.api, "channel_balance", return_value=100)
        mocker.patch.object(node.api, "send_message", return_value=1)
        mocker.patch.object(
            node.api,
            "messages_pop_all",
            side_effect=[["" for _ in range(randint(5, 10))] for _ in range(10)],
        )

        setattr(node.params, "distribution", Parameters())
        setattr(node.params.distribution, "delay_between_two_messages", 0.001)

        await node._retrieve_address()

    setattr(core.params, "subgraph", Parameters())
    setattr(core.params.subgraph, "safes_balance_query", "safes query")
    setattr(core.params.subgraph, "safes_balance_url", "safes default url")
    setattr(core.params.subgraph, "safes_balance_url_backup", "safes backup url")
    setattr(core.params.subgraph, "pagination_size", 100)
    setattr(core.params.subgraph, "from_address", "0x0000")
    setattr(core.params.subgraph, "wxhopr_txs_query", "txs query")
    setattr(core.params.subgraph, "wxhopr_txs_url", "txs url")

    setattr(core.params, "peer", Parameters())
    setattr(core.params.peer, "min_version", "0.0.0")

    setattr(core.params, "economic_model", Parameters())
    setattr(core.params.economic_model, "min_safe_allowance", 0.000001)
    setattr(core.params.economic_model, "filename", "file")

    setattr(core.params, "gcp", Parameters())
    setattr(core.params.gcp, "bucket", "ctdapp-bucket")
    setattr(core.params.gcp, "file_prefix", "prefix")
    setattr(core.params.gcp, "folder", "ctdapp-folder")

    setattr(core.params, "distribution", Parameters())
    setattr(core.params.distribution, "message_delivery_delay", 1)

    await core.healthcheck()

    return core


def test_subgraph_safes_balance_url(core: Core):
    assert core.subgraph_safes_balance_url(SubgraphType.DEFAULT) == "safes default url"
    assert core.subgraph_safes_balance_url(SubgraphType.BACKUP) == "safes backup url"
    assert core.subgraph_safes_balance_url("random") is None


@pytest.mark.asyncio
async def test__retrieve_address(core: Core, address: list[dict]):
    await core._retrieve_address()

    assert core.address == Address(address[-1]["hopr"], address[-1]["native"])


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
    rewards, iter = await core.multiple_attempts_sending(peers[:-1], max_iter)

    assert iter == max_iter
    assert len(rewards) == len(peers) - 1
    assert all([reward["remaining"] >= 0 for reward in rewards.values()])


for p in patches:
    p.stop()
