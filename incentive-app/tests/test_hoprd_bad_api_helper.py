import pytest
from tools.hopr_api_helper import HoprdAPIHelper


@pytest.fixture
def bad_api_helper():
    """
    This fixture returns an instance of the HoprdAPIHelper class.
    """
    apihost = "localhost"
    port = "13301"
    apikey = "some_bad_api_key"

    helper = HoprdAPIHelper(f"http://{apihost}:{port}", apikey)

    yield helper


def test_withdraw(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the withdraw method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_balance(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.balance()

    assert result is None


@pytest.mark.asyncio
async def test_set_alias(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the set_alias method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_get_alias(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the get_alias method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_remove_alias(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the remove_alias method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass


@pytest.mark.asyncio
async def test_get_settings(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the get_settings method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.get_settings()

    assert result is None


@pytest.mark.asyncio
async def test_get_all_channels(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the get_all_channels method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.get_all_channels(True)

    assert result is None


@pytest.mark.asyncio
async def test_get_tickets_in_channel(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the get_tickets_in_channel method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.get_tickets_in_channel(True)

    assert result is None


@pytest.mark.asyncio
async def test_redeem_tickets_in_channel(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the redeem_tickets_in_channel method of the HoprdAPIHelper class returns the
    expected response.
    """

    pass


@pytest.mark.asyncio
async def test_redeem_tickets(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the redeem_tickets method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.redeem_tickets()

    assert result is None


@pytest.mark.asyncio
async def test_ping(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the ping method of the HoprdAPIHelper class returns the
    expected response.
    """
    # peer_ids: list = await bad_api_helper.peers("peerId")
    # latency = await bad_api_helper.ping(peer_ids.pop())

    pass


@pytest.mark.asyncio
async def test_peers(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the peers method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.peers("peerId")

    assert result is None


@pytest.mark.asyncio
async def test_get_address(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the get_address method of the HoprdAPIHelper class returns the
    expected response.
    """
    result = await bad_api_helper.get_address("hopr")

    assert result is None


@pytest.mark.asyncio
async def test_send_message(bad_api_helper: HoprdAPIHelper):
    """
    This test checks that the send_message method of the HoprdAPIHelper class returns the
    expected response.
    """
    pass
