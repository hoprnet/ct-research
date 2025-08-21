import pytest

from core.api.response_objects import Channels
from core.components.balance import Balance

from .conftest import Node, Peer


@pytest.mark.asyncio
async def test_retrieve_address(node: Node, addresses: dict):
    await node.retrieve_address()

    assert getattr(node.address, "native") in [addr["native"] for addr in addresses]


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
    assert isinstance(balances.hopr, Balance)
    assert isinstance(balances.native, Balance)


@pytest.mark.asyncio
async def test_retrieve_peers(node: Node, peers: list[Peer]):
    node.peers = set()
    node.peer_history = dict()
    await node.retrieve_peers()

    assert len(node.peers) == len(peers) - 1
    assert node.peer_history != dict()


@pytest.mark.asyncio
async def test_retrieve_channels(node: Node, channels: Channels):
    assert node.channels is None

    await node.retrieve_channels()

    assert node.channels == channels


@pytest.mark.asyncio
async def test_get_total_channel_funds(node: Node, channels: Channels):
    await node.retrieve_channels()

    total_funds_from_node = await node.get_total_channel_funds()
    total_funds_from_fixture = sum([c.balance for c in channels.outgoing], Balance.zero("wxHOPR"))

    assert total_funds_from_fixture == total_funds_from_node
