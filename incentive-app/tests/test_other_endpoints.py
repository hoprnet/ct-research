import pytest
import aiohttp
from unittest.mock import patch
from economic_handler.economic_handler import EconomicHandler


@pytest.mark.asyncio
async def test_blacklist_rpch_nodes():
    """
    Test whether the method returns the correct list of rpch entry and exit nodes by
    mocking the response and patching the aiohttp.ClientSession.get method to return
    the mocked response.
    """
    mock_response_data = [
        {"id": "1"},
        {"id": "2"},
        {"id": "3"},
    ]

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = mock_get.return_value.__aenter__.return_value
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data

        node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

        result = await node.blacklist_rpch_nodes("some_api_endpoint")

        assert result == ("rpch", ["1", "2", "3"])


@pytest.mark.asyncio
async def test_blacklist_rpch_nodes_exceptions():
    """
    Test whether a connection failure triggers anz of the errors by patching
    the aiohttp.ClientSession.get method of the original function.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Simulate ClientError
        mock_get.side_effect = aiohttp.ClientError("ClientError")
        node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])

        # Simulate ValueError
        mock_get.side_effect = ValueError("ValueError")
        node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])

        # Simulate general exception
        mock_get.side_effect = Exception("Exception")
        node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])
