import pytest
from tools.hopr_api_helper import HoprdAPIHelper

pytest.skip(allow_module_level=True)


@pytest.fixture
def api_helper():
    """
    This fixture returns an instance of the HoprdAPIHelper class.
    """
    apihost = "localhost"
    port = "13301"
    apikey = "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%"

    helper = HoprdAPIHelper(f"http://{apihost}:{port}", apikey)

    yield helper


@pytest.mark.asyncio
async def test_withdraw(api_helper: HoprdAPIHelper):
    """
    This test checks that the withdraw method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_balance(api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response.
    """
    balance = await api_helper.balance()

    assert balance is not None
    assert "native" in balance
    assert "hopr" in balance


@pytest.mark.asyncio
async def test_set_alias(api_helper: HoprdAPIHelper):
    """
    This test checks that the set_alias method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_get_alias(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_alias method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_remove_alias(api_helper: HoprdAPIHelper):
    """
    This test checks that the remove_alias method of the HoprdAPIHelper class returns
    the expected response.
    """
    pass


@pytest.mark.asyncio
async def test_get_settings(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_settings method of the HoprdAPIHelper class returns
    the expected response.
    """
    settings = await api_helper.get_settings()

    assert settings is not None
    assert isinstance(settings, dict)


@pytest.mark.asyncio
async def test_get_all_channels(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_all_channels method of the HoprdAPIHelper class returns
    the expected response.
    """
    await api_helper.get_all_channels(True)


@pytest.mark.asyncio
async def test_get_channel_topology(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_channel_topology method of the HoprdAPIHelper class
    returns the expected response.
    """
    topology = await api_helper.get_channel_topology(True)

    assert topology is not None
    assert isinstance(topology, dict)
    assert "incoming" in topology
    assert "outgoing" in topology
    assert "all" in topology


@pytest.mark.asyncio
async def test_get_tickets_in_channel(api_helper: HoprdAPIHelper):
    """
    This test checks that the get_tickets_in_channel method of the HoprdAPIHelper class
    returns the expected response.
    """
    await api_helper.get_tickets_in_channel(True)


@pytest.mark.asyncio
async def test_redeem_tickets_in_channel(api_helper: HoprdAPIHelper):
    """
    This test checks that the redeem_tickets_in_channel method of the HoprdAPIHelper
    class returns the expected response.
    """
    pass


@pytest.mark.asyncio
async def test_redeem_tickets(api_helper: HoprdAPIHelper):
    """
    This test checks that the redeem_tickets method of the HoprdAPIHelper class returns
    the expected response.
    """
    await api_helper.redeem_tickets()


@pytest.mark.asyncio
async def test_ping(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response.
    """
    peer_ids: list = await api_helper.peers("peerId")
    latency = await api_helper.ping(peer_ids.pop())

    assert latency is not None
    assert isinstance(latency, int)


@pytest.mark.asyncio
async def test_ping_bad_metric(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response when the peerId does not exist.
    """
    peer_ids: list = await api_helper.peers("peerId")
    latency = await api_helper.ping(peer_ids.pop(), metric="some_param")

    assert latency is None


@pytest.mark.asyncio
async def test_peers(api_helper: HoprdAPIHelper):
    """
    This test checks that the peers method of the HoprdAPIHelper class returns the
    expected response.
    """
    peer_ids = await api_helper.peers("peerId")

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
    result = await api_helper.peers("some_param")

    assert result is None


@pytest.mark.asyncio
async def test_ping_bad_status(api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response when the status does not exist.
    """
    peer_ids: list = await api_helper.peers(status="some_status")

    assert peer_ids is None


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
