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

        node = EconomicHandler(
            "some_url",
            "some_api_key",
            "some_rpch_endpoint",
            "some_subgraph_url",
        )

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
        node = EconomicHandler(
            "some_url",
            "some_api_key",
            "some_rpch_endpoint",
            "some_subgraph_url",
        )
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])

        # Simulate ValueError
        mock_get.side_effect = OSError("ValueError")
        node = EconomicHandler(
            "some_url",
            "some_api_key",
            "some_rpch_endpoint",
            "some_subgraph_url",
        )
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])

        # Simulate general exception
        mock_get.side_effect = Exception("Exception")
        node = EconomicHandler(
            "some_url",
            "some_api_key",
            "some_rpch_endpoint",
            "some_subgraph_url",
        )
        result = await node.blacklist_rpch_nodes("some_api_endpoint")
        assert result == ("rpch", [])


# @pytest.mark.asyncio
# async def test_get_staking_participations():
#     """
#     Test whether the method returns the correct dictionary containing the link
#     between safe addresses and stake by mocking the response and patching the
#     aiohttp.ClientSession.get method to return the mocked response.
#     """
#     mock_response_data = {
#         "data": {
#             "stakingParticipations": [
#                 {
#                     "id": "1",
#                     "account": {
#                         "id": "0x1234567890abcdef",
#                     },
#                     "stakingSeason": {
#                         "id": "0x65c39e6bd97f80b5ae5d2120a47644578fd2b8dc",
#                     },
#                     "actualLockedTokenAmount": "1000000000000000000",
#                 },
#                 {
#                     "id": "2",
#                     "account": {
#                         "id": "0xabcdef1234567890",
#                     },
#                     "stakingSeason": {
#                         "id": "0x65c39e6bd97f80b5ae5d2120a47644578fd2b8dc",
#                     },
#                     "actualLockedTokenAmount": "500000000000000000",
#                 },
#             ]
#         }
#     }

#     with patch("aiohttp.ClientSession.post") as mock_post:
#         mock_response = mock_post.return_value.__aenter__.return_value
#         mock_response.status = 200
#         mock_response.json.return_value = mock_response_data

#         node = EconomicHandler(
#             "some_url",
#             "some_api_key",
#             "some_rpch_endpoint",
#             "some_subgraph_url",
#         )

#         result = await node.get_staking_participations(
#             "some_subgraph_url", "some_staking_season_address", 100
#         )

#         assert result == (
#             "subgraph_data",
#             {
#                 "0x1234567890abcdef": 1,
#                 "0xabcdef1234567890": 0.5,
#             },
#         )


# @pytest.mark.asyncio
# async def test_get_staking_participations_exceptions():
#     """
#     Test whether a connection failure triggers anz of the errors by patching
#     the aiohttp.ClientSession.get method of the original function.
#     """
#     with patch("aiohttp.ClientSession.post") as mock_post:
#         # Simulate ClientError

#         mock_post.side_effect = aiohttp.ClientError("ClientError")
#         node = EconomicHandler(
#             "some_url",
#             "some_api_key",
#             "some_rpch_endpoint",
#             "some_subgraph_url",
#         )
#         result = await node.get_staking_participations(  # noqa: F841
#             "some_subgraph_url", "some_staking_season_address", 100
#         )
#         assert result == ("subgraph_data", {})

#         # Simulate ValueError
#         mock_post.side_effect = ValueError("ValueError")
#         node = EconomicHandler(
#             "some_url",
#             "some_api_key",
#             "some_rpch_endpoint",
#             "some_subgraph_url",
#         )
#         result = await node.get_staking_participations(
#             "some_subgraph_url", "some_staking_season_address", 100
#         )
#         assert result == ("subgraph_data", {})

#         # Simulate general exception
#         mock_post.side_effect = Exception("Exception")
#         node = EconomicHandler(
#             "some_url",
#             "some_api_key",
#             "some_rpch_endpoint",
#             "some_subgraph_url",
#         )
#         result = await node.get_staking_participations(
#             "some_subgraph_url", "some_staking_season_address", 100
#         )
#         assert result == ("subgraph_data", {})
