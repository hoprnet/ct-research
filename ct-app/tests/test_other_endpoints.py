import asyncio
import pytest
import aiohttp
from unittest.mock import patch
from economic_handler.economic_handler import EconomicHandler


def create_node():
    return EconomicHandler(
        "some_url", "some_api_key", "some_rpch_endpoint", "some_subgraph_url"
    )


# @pytest.mark.asyncio
# async def test_get_rpch_nodes():
#     """
#     Test whether the method returns the correct list of rpch entry and exit nodes by
#     mocking the response and patching the aiohttp.ClientSession.get method to return
#     the mocked response.
#     """
#     mock_response_data = [
#         {"id": "1"},
#         {"id": "2"},
#         {"id": "3"},
#     ]

#     with patch("aiohttp.ClientSession.get") as mock_get:
#         mock_response = mock_get.return_value.__aenter__.return_value
#         mock_response.status = 200
#         mock_response.json.return_value = mock_response_data

#         node = create_node()
#         node.started = True

#         asyncio.create_task(node.get_rpch_nodes())
#         await asyncio.sleep(0.5)

#         node.started = False
#         await asyncio.sleep(0.5)

#         assert node.rpch_nodes == ["1", "2", "3"]


# @pytest.mark.asyncio
# async def test_get_rpch_nodes_exceptions():
#     """
#     Test whether a connection failure triggers anz of the errors by patching
#     the aiohttp.ClientSession.get method of the original function.
#     """
#     with patch("aiohttp.ClientSession.get") as mock_get:
#         node = create_node()
#         # Simulate ClientError
#         mock_get.side_effect = aiohttp.ClientError("ClientError")
#         asyncio.create_task(node.get_rpch_nodes())
#         await asyncio.sleep(0.5)
#         node.started = False
#         await asyncio.sleep(0.5)
#         assert node.rpch_nodes is None

#         # Simulate ValueError
#         mock_get.side_effect = OSError("ValueError")
#         asyncio.create_task(node.get_rpch_nodes())
#         await asyncio.sleep(0.5)
#         node.started = False
#         await asyncio.sleep(0.5)
#         assert node.rpch_nodes is None

#         # Simulate general exception
#         mock_get.side_effect = Exception("Exception")
#         asyncio.create_task(node.get_rpch_nodes())
#         await asyncio.sleep(0.5)
#         node.started = False
#         await asyncio.sleep(0.5)
#         assert node.rpch_nodes is None


@pytest.mark.asyncio
async def test_get_subgraph_data():
    """
    Test whether the method returns the correct dictionary containing the link
    between safe addresses and node addresses and balance by mocking the response
    and patching the aiohttp.ClientSession.get method to return the mocked response.
    """
    mock_response_data = {
        "data": {
            "safes": [
                {
                    "registeredNodesInNetworkRegistry": [
                        {
                            "node": {"id": "node_1"},
                            "safe": {
                                "id": "safe_1",
                                "balance": {"wxHoprBalance": "100"},
                            },
                        }
                    ]
                }
            ]
        }
    }

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_response = mock_post.return_value.__aenter__.return_value
        mock_response.status = 200
        mock_response.json.return_value = mock_response_data

        node = create_node()
        node.started = True
        asyncio.create_task(node.get_subgraph_data())
        await asyncio.sleep(0.5)

        # avoid infinite while loop by setting node.started = False
        node.started = False
        await asyncio.sleep(0.5)

        expected_data = {"node_1": {"safe_address": "safe_1", "wxHOPR_balance": "100"}}

        assert node.subgraph_dict == expected_data


@pytest.mark.asyncio
async def test_get_get_subgraph_data_exceptions():
    """
    Test whether a connection failure triggers any of the errors by patching
    the aiohttp.ClientSession.get method of the original function.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        node = create_node()
        # Simulate ClientError
        mock_get.side_effect = aiohttp.ClientError("ClientError")
        asyncio.create_task(node.get_subgraph_data())
        await asyncio.sleep(0.5)
        node.started = False
        await asyncio.sleep(0.5)
        assert node.subgraph_dict is None

        # Simulate ValueError
        mock_get.side_effect = OSError("ValueError")
        asyncio.create_task(node.get_subgraph_data())
        await asyncio.sleep(0.5)
        node.started = False
        await asyncio.sleep(0.5)
        assert node.subgraph_dict is None

        # Simulate general exception
        mock_get.side_effect = Exception("Exception")
        asyncio.create_task(node.get_subgraph_data())
        await asyncio.sleep(0.5)
        node.started = False
        await asyncio.sleep(0.5)
        assert node.subgraph_dict is None
