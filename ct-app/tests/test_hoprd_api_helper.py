import os
import pytest
from tools.hopr_api_helper import HoprdAPIHelper
from tools import envvar

os.environ["API_HOST"] = "foo_host"
os.environ["API_PORT"] = "foo_port"
os.environ["API_TOKEN"] = "foo_token"


@pytest.fixture
def api_helper():
    """
    This fixture returns an instance of the HoprdAPIHelper class.
    """

    apihost = envvar("API_HOST")
    apiport = envvar("API_PORT")
    apikey = envvar("API_TOKEN")

    helper = HoprdAPIHelper(f"http://{apihost}:{apiport}", apikey)

    yield helper


@pytest.mark.asyncio
async def test_balance_native(api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when only the native balance is requested.
    """
    native_balance = await api_helper.balances("native")

    assert native_balance is not None
    assert isinstance(native_balance, int)


@pytest.mark.asyncio
async def test_get_all_channels(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_all_channels method of the HoprdAPIHelper class returns
    the expected response.
    """
    await api_helper.all_channels(True)


@pytest.mark.asyncio
async def test_ping(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response.
    """
    peer_ids: list = await api_helper.peers("peer_id")
    latency = await api_helper.ping(peer_ids.pop())

    assert latency != 0
    assert isinstance(latency, int)


@pytest.mark.asyncio
async def test_ping_bad_metric(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response when the peerId does not exist.
    """
    peer_ids: list = await api_helper.peers("peer_id")
    latency = await api_helper.ping(peer_ids.pop(), metric="some_param")

    assert latency == 0


@pytest.mark.asyncio
async def test_peers(api_helper: HoprdAPIHelper):
    """
    This test checks that the peers method of the HoprdAPIHelper class returns the
    expected response.
    """
    peer_ids = await api_helper.peers("peer_id")

    assert peer_ids is not None
    assert isinstance(peer_ids, list)
    assert len(peer_ids) > 0
    assert isinstance(peer_ids[0], str)


@pytest.mark.asyncio
async def test_get_peers_bad_param(api_helper: HoprdAPIHelper):
    """
    This test checks that the peers method of the HoprdAPIHelper class returns the
    expected response when the peerId does not exist.
    """
    peer_ids = await api_helper.peers("some_param")

    assert isinstance(peer_ids, list)
    assert len(peer_ids) == 0


@pytest.mark.asyncio
async def test_ping_bad_status(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response when the status does not exist.
    """
    peer_ids: list = await api_helper.peers(status="some_status")

    assert isinstance(peer_ids, list)
    assert len(peer_ids) == 0


@pytest.mark.asyncio
async def test_get_address(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_address method of the HoprdAPIHelper class returns the
    expected response.
    """
    address = await api_helper.get_address("hopr")

    assert address is not None
    assert isinstance(address, str)


@pytest.mark.asyncio
async def test_get_bad_address(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_address method of the HoprdAPIHelper class returns the
    expected response when the address name does not exist.
    """
    address = await api_helper.get_address("some_bad_address")

    assert address is None


@pytest.mark.asyncio
async def test_send_message(api_helper: HoprdAPIHelper):
    """
    This test checks that the send_message method of the HoprdAPIHelper class returns
    the expected response.
    """
    pass
