import inspect

import pytest

from core.api.response_objects import Channels

from .conftest import Node, Peer


@pytest.mark.asyncio
async def test_retrieve_address(node: Node, addresses: dict):
    await node.retrieve_address()

    assert node.address is not None
    assert node.address.native in [addr["native"] for addr in addresses]
    assert node.address.hopr in [addr["hopr"] for addr in addresses]


@pytest.mark.asyncio
async def test_node_healthcheck(node: Node):
    await node.healthcheck()
    assert node.connected


@pytest.mark.asyncio
async def test_retrieve_balances(node: Node):
    await node.healthcheck()

    balances = await node.retrieve_balances()

    assert balances.hopr is not None
    assert balances.native is not None
    assert isinstance(balances.hopr, int)
    assert isinstance(balances.native, int)


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
async def test_retrieve_channels(node: Node, channels: Channels):
    assert node.channels is None

    await node.retrieve_channels()

    assert node.channels == channels


@pytest.mark.asyncio
async def test_get_total_channel_funds(node: Node, channels: Channels):
    await node.retrieve_channels()

    total_funds_from_node = await node.get_total_channel_funds()
    total_funds_from_fixture = sum([int(c.balance) for c in channels.outgoing])

    assert total_funds_from_fixture / 1e18 == total_funds_from_node


@pytest.mark.asyncio
async def test_check_inbox(node: Node):
    pytest.skip(f"{inspect.stack()[0][3]} not implemented")


@pytest.mark.asyncio
async def test_fromAddressAndKeyLists(node: Node):
    addresses = ["LOCALHOST:9091", "LOCALHOST:9092", "LOCALHOST:9093"]
    keys = ["key1", "key2", "key3"]

    nodes = Node.fromCredentials(addresses, keys)

    assert len(nodes) == len(addresses) == len(keys)
    assert len(nodes) == len(addresses) == len(keys)
