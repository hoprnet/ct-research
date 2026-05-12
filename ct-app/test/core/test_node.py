import asyncio
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from core.api.response_objects import Addresses, Channels
from core.node import Node
from core.types.balance import Balance
from core.types.peer import Peer


@pytest.mark.asyncio
async def test_retrieve_address(node: Node, addresses: dict):
    await node.retrieve_address()

    assert getattr(node.address, "native") in [addr["native"] for addr in addresses]


@pytest.mark.asyncio
async def test_retrieve_address_prefers_green_destinations(
    node: Node, addresses: list[dict], mocker
):
    node.params.sessions.green_destinations = [addresses[0]["native"], addresses[1]["native"]]
    node.params.sessions.blue_destinations = [addresses[0]["native"], addresses[2]["native"]]

    await node.retrieve_address()

    assert node.session_destinations == [addresses[1]["native"]]


@pytest.mark.asyncio
async def test_retrieve_address_clears_destinations_when_address_not_in_any_group(
    node: Node, addresses: list[dict]
):
    node.params.sessions.green_destinations = [addresses[0]["native"], addresses[1]["native"]]
    node.params.sessions.blue_destinations = [addresses[0]["native"], addresses[2]["native"]]
    await node.retrieve_address()
    assert node.session_destinations == [addresses[1]["native"]]

    node.params.sessions.green_destinations = [addresses[3]["native"]]
    node.params.sessions.blue_destinations = [addresses[4]["native"]]

    await node.retrieve_address()

    assert node.session_destinations == []


@pytest.mark.asyncio
async def test_retrieve_address_retries_until_api_returns_value(
    node: Node, addresses: list[dict], mocker
):
    sleep_mock = AsyncMock()
    mocker.patch("core.mixins.state.asyncio.sleep", sleep_mock)
    mocker.patch.object(
        node.api,
        "address",
        side_effect=[None, None, Addresses(addresses[0])],
    )

    await node.retrieve_address(retry_delay=0.5)

    assert node.address.native == addresses[0]["native"]
    assert sleep_mock.await_count == 2
    sleep_mock.assert_awaited_with(0.5)


@pytest.mark.asyncio
async def test_ticket_parameters_updates_cached_ticket_price(node: Node, mocker):
    async def stream_ticket_parameters():
        yield SimpleNamespace(
            ticket_price=Balance("0.0001 wxHOPR"),
            min_ticket_winning_probability=0.5,
        )
        raise asyncio.CancelledError

    mocker.patch.object(
        node.blokli_repository,
        "stream_ticket_parameters",
        side_effect=stream_ticket_parameters,
    )
    network_update_request = mocker.patch.object(node.network_update_coordinator, "request")

    with pytest.raises(asyncio.CancelledError):
        await node.ticket_parameters()

    assert node.ticket_price is not None
    assert node.ticket_price.value == Balance("0.0001 wxHOPR")
    assert node.min_ticket_winning_probability == 0.5
    network_update_request.assert_called_once_with("ticket_parameters_subscription")


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
    node.peers = {}
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
