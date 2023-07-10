import asyncio
import functools
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

from netwatcher import NetWatcher  # noqa: E402
from tools.hopr_api_helper import HoprdAPIHelper  # noqa: E402


# TODO: add tests for the following methods:
# - wipe_peers
# - _post_list
# - gather_peers
# - ping_peers
# - transmit_peers
# - connect


def FakeNetWatcher() -> NetWatcher:
    """Fixture that returns a mock instance of a NetWatcher"""
    return NetWatcher("some_url", "some_key", "some_posturl", 10)


def test_wipe_peers():
    """
    Test that the method wipes the peers and latency attributes.
    """
    instance = FakeNetWatcher()
    instance.peers.add("some_peer")
    instance.peers.add("some other peer")

    instance.latency = {"some_peer_id": 10}

    instance.wipe_peers()

    assert len(instance.peers) == 0
    assert len(instance.latency) == 0


def test__post_list():
    """
    Test that the method posts the peers and latency to the aggregator.
    """
    pass


@pytest.fixture
def mock_instance_for_test_gather(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """

    api = HoprdAPIHelper("some_url", "some_key")
    mocker.patch.object(api, "peers", return_value=["some_peer", "some_other_peer"])

    instance = NetWatcher("some_url", "some_key", "some_posturl")
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

    instance = NetWatcher("some_url", "some_key", "some_posturl")
    instance.peers = ["some_peer", "some_other_peer"]
    instance.api = api

    return instance


@pytest.mark.asyncio
async def test_ping_peers(mock_instance_for_test_ping: NetWatcher):
    """
    Test that the method pings peers works.
    """
    instance = mock_instance_for_test_ping

    instance.peer_id = "some_peer_id"
    instance.started = True

    asyncio.create_task(instance.ping_peers())
    await asyncio.sleep(1)

    # avoid infinite while loop by setting node.started = False
    instance.started = False
    await asyncio.sleep(1)

    assert len(instance.latency) == 2


@pytest.fixture
def mock_instance_for_test_transmit(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """

    instance = NetWatcher("some_url", "some_key", "some_posturl")
    instance.peers = ["some_peer", "some_other_peer"]
    instance.latency = {"some_peer": 10, "some_other_peer": 20}
    mocker.patch.object(instance, "_post_list", return_value=True)

    return instance


@pytest.mark.asyncio
async def test_transmit_peers(mock_instance_for_test_transmit: NetWatcher):
    """
    Test that the method transmits peers works.
    """
    instance = mock_instance_for_test_transmit

    instance.peer_id = "some_peer_id"
    instance.started = True

    asyncio.create_task(instance.transmit_peers())
    await asyncio.sleep(1)

    # avoid infinite while loop by setting node.started = False
    instance.started = False
    await asyncio.sleep(1)

    assert instance._post_list.called


@pytest.fixture
def mock_instance_for_test_start(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """
    mocker.patch.object(NetWatcher, "connect", return_value=None)
    mocker.patch.object(NetWatcher, "gather_peers", return_value=None)
    mocker.patch.object(NetWatcher, "ping_peers", return_value=None)
    mocker.patch.object(NetWatcher, "transmit_peers", return_value=None)

    return NetWatcher("some_url", "some_api_key", "some_rpch_endpoint")


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

    assert len(instance.tasks) == 4

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
