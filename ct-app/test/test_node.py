import asyncio
import time
from random import randint, random
from test.decorators_patches import patches

import pytest
from core.components.parameters import Parameters
from core.model.address import Address
from hoprd_sdk.models import ChannelTopology, InlineResponse2006
from pytest_mock import MockerFixture

for p in patches:
    p.start()

# needs to be imported after the patches are applied
from core.node import Node  # noqa: E402


@pytest.fixture
def peers() -> list[dict]:
    return [
        {"peer_id": "id_0", "peer_address": "address_0", "reported_version": "1.0.0"},
        {"peer_id": "id_1", "peer_address": "address_1", "reported_version": "1.0.0"},
        {"peer_id": "id_2", "peer_address": "address_2", "reported_version": "1.0.0"},
        {"peer_id": "id_3", "peer_address": "address_3", "reported_version": "1.0.0"},
    ]


@pytest.fixture
def channels(peers: list[dict]) -> InlineResponse2006:
    channels = list[ChannelTopology]()
    index = 0

    for src in peers:
        for dest in peers:
            if src["peer_address"] == dest["peer_address"]:
                continue

            channels.append(
                ChannelTopology(
                    f"channel_{index}",
                    src["peer_id"],
                    dest["peer_id"],
                    src["peer_address"],
                    dest["peer_address"],
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
def address() -> dict:
    return {"hopr": "id_0", "native": "address_0"}


@pytest.fixture
async def node(
    mocker: MockerFixture,
    peers: list[dict],
    channels: InlineResponse2006,
    address: dict,
) -> Node:
    node = Node("localhost", "random_key")

    mocker.patch.object(node.api, "all_channels", return_value=channels)
    mocker.patch.object(node.api, "peers", return_value=peers[1:])
    mocker.patch.object(node.api, "get_address", return_value=address)
    mocker.patch.object(node.api, "balances", return_value={"hopr": 10, "native": 1})
    mocker.patch.object(node.api, "channel_balance", return_value=100)
    mocker.patch.object(node.api, "send_message", return_value=1)

    setattr(node.params, "distribution", Parameters())
    setattr(node.params.distribution, "delay_between_two_messages", 0.2)

    await node.healthcheck()

    return node


@pytest.mark.asyncio
async def test__retrieve_address(node: Node, address: dict):
    await node._retrieve_address()

    assert node.address == Address(address["hopr"], address["native"])


@pytest.mark.asyncio
async def test_healthcheck(node: Node):
    await node.healthcheck()

    assert await node.connected.get()


@pytest.mark.asyncio
async def test_retrieve_balances(node: Node):
    await node.healthcheck()

    balances = await node.retrieve_balances()

    assert balances.get("hopr", None) is not None
    assert balances.get("native", None) is not None
    assert isinstance(balances.get("hopr"), int)
    assert isinstance(balances.get("native"), int)


@pytest.mark.asyncio
async def test_open_channels(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_close_incoming_channels(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_close_pending_channels(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_close_old_channels(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_fund_channels(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_retrieve_peers(node: Node, peers: list[dict]):
    assert await node.peers.get() == set()
    assert await node.peer_history.get() == dict()

    await node.retrieve_peers()

    assert len(await node.peers.get()) == len(peers) - 1
    assert await node.peer_history.get() != dict()


@pytest.mark.asyncio
async def test_retrieve_outgoing_channels(node: Node, channels: InlineResponse2006):
    assert await node.outgoings.get() == []

    await node.retrieve_outgoing_channels()

    outgoings_from_node = await node.outgoings.get()
    outgoings_from_fixture = [
        c for c in channels.all if c.source_peer_id == node.address.id
    ]

    assert [c.channel_id for c in outgoings_from_node] == [
        c.channel_id for c in outgoings_from_fixture
    ]


@pytest.mark.asyncio
async def test_retrieve_incoming_channels(node: Node, channels: InlineResponse2006):
    assert await node.incomings.get() == []

    await node.retrieve_incoming_channels()

    incomings_from_node = await node.incomings.get()
    incomings_from_fixture = [
        c for c in channels.all if c.destination_peer_id == node.address.id
    ]

    assert [c.channel_id for c in incomings_from_node] == [
        c.channel_id for c in incomings_from_fixture
    ]


@pytest.mark.asyncio
async def test_get_total_channel_funds(node: Node, channels: InlineResponse2006):
    await node.retrieve_outgoing_channels()

    total_funds_from_node = await node.get_total_channel_funds()
    total_funds_from_fixture = sum(
        [int(c.balance) for c in channels.all if c.source_peer_id == node.address.id]
    )

    assert total_funds_from_fixture / 1e18 == total_funds_from_node


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_tasks,sleep", [(randint(10, 20), round(random() * 0.3 + 0.2, 2))]
)
async def test__delay_message(node: Node, num_tasks: int, sleep: float):
    tasks = set[asyncio.Task]()

    for idx in range(num_tasks):
        tasks.add(
            asyncio.create_task(
                node._delay_message(idx, "random_relayer", 0, sleep * idx)
            )
        )

    before = time.time()
    issued = await asyncio.gather(*tasks)
    after = time.time()

    assert after - before <= sleep * num_tasks
    assert after - before >= sleep * (num_tasks - 1)
    assert sum(issued) == num_tasks


@pytest.mark.asyncio
async def test_distribute_rewards(node: Node):
    await node.retrieve_peers()

    peer_group = {}
    for idx, peer in enumerate(await node.peers.get()):
        message_count = randint(4, 10)

        peer_group[peer.address.id] = {
            "expected": message_count,
            "remaining": message_count,
            "issued": 0,
            "tag": idx,
            "ticket-price": 0.01,
        }

    issued_count = await node.distribute_rewards(peer_group)

    assert len(issued_count) == len(peer_group)
    assert all([v != 0 for v in issued_count.values()])


@pytest.mark.asyncio
async def test_check_inbox(node: Node):
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_fromAddressAndKeyLists(node: Node):
    addresses = ["LOCALHOST:9091", "LOCALHOST:9092", "LOCALHOST:9093"]
    keys = ["key1", "key2", "key3"]

    nodes = Node.fromAddressAndKeyLists(addresses, keys)

    assert len(nodes) == len(addresses) == len(keys)


for p in patches:
    p.stop()
