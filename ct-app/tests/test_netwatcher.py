import asyncio
import functools
import os
import time
from unittest.mock import MagicMock, patch
import pytest


def mock_decorator(*args, **kwargs):
    """Decorate by doing nothing."""

    def decorator(func):
        @functools.wraps(func)
        async def decorated_function(*args, **kwargs):
            return await func(*args, **kwargs)

        return decorated_function

    return decorator


# PATCH THE DECORATOR HERE
patch("tools.decorator.wakeupcall", mock_decorator).start()
patch("tools.decorator.formalin", mock_decorator).start()

from netwatcher import NetWatcher, Peer, Address  # noqa: E402
from tools.hopr_api_helper import HoprdAPIHelper  # noqa: E402


def FakeNetWatcher() -> NetWatcher:
    """Fixture that returns a mock instance of a NetWatcher"""
    return NetWatcher("some_url", "some_key", "some_posturl", "some_balanceurl", 10)


@pytest.fixture
def mock_instance_for_test_gather(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """

    api = HoprdAPIHelper("some_url", "some_key")
    mocker.patch.object(
        api,
        "peers",
        return_value=[
            {"peer_id": "some_peer", "peer_address": "some_address"},
            {"peer_id": "some_other_peer", "peer_address": "some_other_address"},
        ],
    )

    instance = NetWatcher("some_url", "some_key", "some_posturl", "some_balanceurl")
    instance.api = api

    return instance


@pytest.mark.asyncio
async def test_gather_peers(mock_instance_for_test_gather: NetWatcher):
    """
    Test that the method gather_peer works
    """
    instance = mock_instance_for_test_gather

    instance.peer_id = "some_peer_id"
    instance.started = True

    asyncio.create_task(instance.gather_peers())
    await asyncio.sleep(1)

    # avoid infinite while loop by setting node.started = False
    instance.started = False
    await asyncio.sleep(1)

    assert len(instance.peers) == 2


@pytest.fixture
def mock_instance_for_test_ping(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """
    api = HoprdAPIHelper("some_url", "some_key")
    mocker.patch.object(api, "ping", return_value=10)

    instance = NetWatcher("some_url", "some_key", "some_posturl", "some_balanceurl")
    instance.peers = [
        Peer(Address("some_peer", "some_address")),
        Peer(Address("some_other_peer", "some_other_address")),
    ]
    instance.api = api

    return instance


@pytest.mark.asyncio
async def test_ping_peers(mock_instance_for_test_ping: NetWatcher):
    """
    Test that the method pings peers works.
    """

    os.environ["MOCK_LATENCY"] = "1"

    instance = mock_instance_for_test_ping

    instance.peer_id = "some_peer_id"
    instance.started = True

    asyncio.create_task(instance.ping_peers())
    await asyncio.sleep(2)

    # avoid infinite while loop by setting node.started = False
    instance.started = False
    await asyncio.sleep(1)

    measures = [peer for peer in instance.peers if peer.latency is not None]

    assert len(measures) == 1


@pytest.fixture
def mock_instance_for_test_transmit(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """

    instance = NetWatcher("some_url", "some_key", "some_posturl", "some_balanceurl")
    instance.peers = [
        Peer(Address("some_peer_1", "some_address_1"), 10, time.time() - 60 * 60),
        Peer(Address("some_peer_2", "some_address_2"), 20, time.time() - 60 * 60),
    ]

    return instance


@pytest.mark.asyncio
async def test_transmit_peers(mock_instance_for_test_transmit: NetWatcher):
    """
    Test that the method transmits peers works.
    """
    instance = mock_instance_for_test_transmit

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = mock_post.return_value.__aenter__.return_value
        mock_response.status = 200

        instance.peer_id = "some_peer_id"
        instance.started = True
        instance.max_lat_count = 2

        await asyncio.create_task(instance.transmit_peers())
        await asyncio.sleep(1)

        # avoid infinite while loop by setting node.started = False
        instance.started = False
        await asyncio.sleep(1)

        assert all(peer.latency is None for peer in instance.peers)


@pytest.fixture
def mock_instance_for_test_transmit_balance(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """
    api = HoprdAPIHelper("some_url", "some_key")
    mocker.patch.object(api, "balances", return_value=10)

    instance = NetWatcher("some_url", "some_key", "some_posturl", "some_balanceurl")
    instance.api = api

    return instance


@pytest.mark.asyncio
async def test_transmit_balance(mock_instance_for_test_transmit_balance: NetWatcher):
    """
    Test that the method transmit_balance works.
    """
    instance = mock_instance_for_test_transmit_balance

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = mock_post.return_value.__aenter__.return_value
        mock_response.status = 200

        instance.peer_id = "some_peer_id"
        instance.started = True

        asyncio.create_task(instance.transmit_balance())
        await asyncio.sleep(1)

        # avoid infinite while loop by setting node.started = False
        instance.started = False
        await asyncio.sleep(1)


@pytest.fixture
def mock_instance_for_test_start(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """
    mocker.patch.object(NetWatcher, "connect", return_value=None)
    mocker.patch.object(NetWatcher, "gather_peers", return_value=None)
    mocker.patch.object(NetWatcher, "ping_peers", return_value=None)
    mocker.patch.object(NetWatcher, "transmit_peers", return_value=None)
    mocker.patch.object(NetWatcher, "transmit_balance", return_value=None)
    mocker.patch.object(NetWatcher, "close_incoming_channels", return_value=None)
    mocker.patch.object(NetWatcher, "handle_channels", return_value=None)

    return NetWatcher("some_url", "some_api_key", "some_posturl", "some_balanceurl")


@pytest.mark.asyncio
async def test_start(mock_instance_for_test_start: NetWatcher):
    """
    Test whether all coroutines were called with the expected arguments.
    """
    instance = mock_instance_for_test_start

    await instance.start()
    await asyncio.sleep(1)

    assert instance.connect.called
    assert instance.gather_peers.called
    assert instance.ping_peers.called
    assert instance.transmit_peers.called
    assert instance.transmit_balance.called
    # assert instance.close_incoming_channels.called
    assert instance.handle_channels.called

    assert len(instance.tasks) == 6

    assert instance.started


def test_stop():
    """
    Test whether the stop method cancels the tasks and updates the 'started' attribute.
    """
    mocked_task = MagicMock()
    instance = FakeNetWatcher()
    instance.tasks = {mocked_task}

    instance.stop()

    assert not instance.started
    mocked_task.cancel.assert_called_once()
    assert instance.tasks == set()
