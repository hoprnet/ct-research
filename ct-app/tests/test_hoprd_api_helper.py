import os

import pytest
from hoprd_sdk.rest import ApiException

from tools import HoprdAPIHelper, envvar

if "API_HOST" not in os.environ:
    os.environ["API_HOST"] = "foo_host"
if "API_PORT" not in os.environ:
    os.environ["API_PORT"] = "foo_port"
if "API_TOKEN" not in os.environ:
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


def test_get_url(api_helper: HoprdAPIHelper):
    """
    Test that the url is protected once set, and only the getter is available.
    """
    url = api_helper.url

    assert len(url) != 0
    with pytest.raises(AttributeError):
        api_helper.url = "some_new_url"


def test_get_token(api_helper: HoprdAPIHelper):
    """
    Test that the token is protected once set, and only the getter is available.
    """
    token = api_helper.token

    assert len(token) != 0
    with pytest.raises(AttributeError):
        api_helper.token = "some_new_token"


@pytest.mark.asyncio
async def test_bad_balance(api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when the requested balance is not supported.
    """
    balance = await api_helper.balance("fake_balance")

    assert balance is None


@pytest.mark.asyncio
async def test_balance_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when an ApiException is raised.
    """

    mocker.patch.object(
        api_helper.account_api, "account_get_balances", side_effect=ApiException
    )
    balance = await api_helper.balance("hopr")
    assert balance is None

    mocker.patch.object(
        api_helper.account_api, "account_get_balances", side_effect=OSError
    )
    balance = await api_helper.balance("hopr")
    assert balance is None


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
async def test_get_all_channels_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when an ApiException is raised.
    """

    mocker.patch.object(
        api_helper.channels_api, "channels_get_channels", side_effect=ApiException
    )
    result = await api_helper.get_all_channels(False)
    assert result is None

    mocker.patch.object(
        api_helper.channels_api, "channels_get_channels", side_effect=OSError
    )
    result = await api_helper.get_all_channels(False)
    assert result is None


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
async def test_ping_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when an ApiException is raised.
    """

    mocker.patch.object(api_helper.node_api, "node_ping", side_effect=ApiException)
    latency = await api_helper.ping("peer_id")
    assert latency == 0

    mocker.patch.object(api_helper.node_api, "node_ping", side_effect=OSError)
    latency = await api_helper.ping("peer_id")
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
async def test_get_peers_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when an ApiException is raised.
    """

    mocker.patch.object(api_helper.node_api, "node_get_peers", side_effect=ApiException)
    peer_ids = await api_helper.peers("peer_id")
    assert isinstance(peer_ids, list)
    assert len(peer_ids) == 0

    mocker.patch.object(api_helper.node_api, "node_get_peers", side_effect=OSError)
    peer_ids = await api_helper.peers("peer_id")
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
async def test_get_address_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the balance method of the HoprdAPIHelper class returns the
    expected response when an ApiException is raised.
    """

    mocker.patch.object(
        api_helper.account_api, "account_get_address", side_effect=ApiException
    )
    address = await api_helper.get_address("hopr")
    assert address is None

    mocker.patch.object(
        api_helper.account_api, "account_get_address", side_effect=OSError
    )
    address = await api_helper.get_address("hopr")
    assert address is None


@pytest.mark.asyncio
async def test_send_message(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the send_message method of the HoprdAPIHelper class returns
    the expected response.
    """

    # dummy AsyncResult object
    class DummyAsyncResult:
        def get(self):
            return "success"

    mocker.patch.object(
        api_helper.message_api, "messages_send_message", return_value=DummyAsyncResult()
    )

    result = await api_helper.send_message("destination", "message", ["hops"])
    assert result is True


@pytest.mark.asyncio
async def test_send_message_exceptions(mocker, api_helper: HoprdAPIHelper):
    """
    This test checks that the send_message method of the HoprdAPIHelper class returns
    the expected response when an ApiException is raised.
    """

    mocker.patch.object(
        api_helper.message_api, "messages_send_message", side_effect=ApiException
    )
    result = await api_helper.send_message("destination", "message", ["hops"])
    assert result is False

    mocker.patch.object(
        api_helper.message_api, "messages_send_message", side_effect=OSError
    )
    result = await api_helper.send_message("destination", "message", ["hops"])
    assert result is False


@pytest.mark.asyncio
async def test_get_unique_nodeAddress_peerId_aggbalance_links(
    api_helper: HoprdAPIHelper,
):
    """
    This test checks that the get_unique_nodeAddress_peerId_aggbalance_links method of
    the HoprdAPIHelper class returns the expected response.
    """

    links = await api_helper.get_unique_nodeAddress_peerId_aggbalance_links()

    assert links is not None
    assert isinstance(links, dict)
    assert len(links) > 0

    for key, value in links.items():
        assert isinstance(key, str)
        assert isinstance(value, dict)
        assert "source_node_address" in value.keys()
        assert "aggregated_balance" in value.keys()


@pytest.mark.asyncio
async def test_get_unique_nodeAddress_peerId_aggbalance_links_exceptions(
    mocker,
    api_helper: HoprdAPIHelper,
):
    """
    This test checks that the get_unique_nodeAddress_peerId_aggbalance_links method of
    the HoprdAPIHelper class returns the expected response.
    """

    mocker.patch.object(
        api_helper.channels_api, "channels_get_channels", side_effect=ApiException
    )
    links = await api_helper.get_unique_nodeAddress_peerId_aggbalance_links()
    assert links is None

    mocker.patch.object(
        api_helper.channels_api, "channels_get_channels", side_effect=OSError
    )
    links = await api_helper.get_unique_nodeAddress_peerId_aggbalance_links()
    assert links is None
