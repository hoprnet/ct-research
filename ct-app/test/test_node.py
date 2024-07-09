import inspect

import pytest
from hoprd_sdk.models import NodeChannelsResponse

from .conftest import Node, Peer


@pytest.mark.asyncio
async def test_retrieve_address(node: Node, addresses: dict):
    await node.retrieve_address()
    address = await node.address.get()

    assert address.address in [addr["native"] for addr in addresses]
    assert address.id in [addr["hopr"] for addr in addresses]


@pytest.mark.asyncio
async def test_node_healthcheck(node: Node):
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
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_close_incoming_channels(node: Node):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_close_pending_channels(node: Node):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_close_old_channels(node: Node):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_fund_channels(node: Node):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_retrieve_peers(node: Node, peers: list[Peer]):
    await node.peers.set(set())
    await node.peer_history.set(dict())
    await node.retrieve_peers()

    assert len(await node.peers.get()) == len(peers) - 1
    assert await node.peer_history.get() != dict()


@pytest.mark.asyncio
async def test_retrieve_outgoing_channels(node: Node, channels: NodeChannelsResponse):
    assert await node.outgoings.get() == []

    await node.retrieve_outgoing_channels()

    outgoings_from_node = await node.outgoings.get()
    outgoings_from_fixture = [
        c for c in channels.all if c.source_peer_id == (await node.address.get()).id
    ]

    assert [c.channel_id for c in outgoings_from_node] == [
        c.channel_id for c in outgoings_from_fixture
    ]


@pytest.mark.asyncio
async def test_retrieve_incoming_channels(node: Node, channels: NodeChannelsResponse):
    assert await node.incomings.get() == []

    await node.retrieve_incoming_channels()

    incomings_from_node = await node.incomings.get()
    incomings_from_fixture = [
        c
        for c in channels.all
        if c.destination_peer_id == (await node.address.get()).id
    ]

    assert [c.channel_id for c in incomings_from_node] == [
        c.channel_id for c in incomings_from_fixture
    ]


@pytest.mark.asyncio
async def test_get_total_channel_funds(node: Node, channels: NodeChannelsResponse):
    await node.retrieve_outgoing_channels()

    total_funds_from_node = await node.get_total_channel_funds()
    total_funds_from_fixture = sum(
        [
            int(c.balance)
            for c in channels.all
            if c.source_peer_id == (await node.address.get()).id
        ]
    )

    assert total_funds_from_fixture / 1e18 == total_funds_from_node


def test_fromCredentials():
    addresses = ["LOCALHOST:9091", "LOCALHOST:9092", "LOCALHOST:9093"]
    keys = ["key1", "key2", "key3"]

    nodes = Node.fromCredentials(addresses, keys)

    assert len(nodes) == len(addresses) == len(keys)
