import asyncio

import pytest

from tools import HOPRNode

# @pytest.mark.asyncio
# async def test_connect_successful(mocker):
#     """
#     Test that the method connects successfully to the HOPR node and sets the correct
#     peer_id attribute value.
#     """
#     node = HOPRNode("some_url", "some_api_key")
#     expected_response = "some_peer_id"

#     mocker.Mock()
#     mocker.patch.object(node.api, "get_address", return_value=expected_response)

#     node.started = True
#     task = asyncio.create_task(node.connect())
#     await asyncio.sleep(1)

#     # avoid infinite while loop by setting node.started = False
#     node.started = False
#     await asyncio.sleep(1)

#     assert node.peer_id == "some_peer_id"
#     await asyncio.gather(task)


def test_disconnect_method():
    """
    Test that the node is disconnected after calling disconnect method
    Test that the peer_id attribute is set to None after calling disconnect method
    """
    node = HOPRNode("some_url", "some_api_key")
    node.peer_id = "some_peer_id"
    node.disconnect()
    assert not node.connected
    assert node.peer_id is None


def test_disconnect_when_not_connected():
    """
    Test that the node is not disconnected when not connected
    """
    node = HOPRNode("some_url", "some_api_key")
    result = node.disconnect()

    assert result is None


@pytest.mark.asyncio
async def test_connect_when_node_available(mocker):
    node = HOPRNode("some_url", "some_api_key")

    mocker.patch.object(node.api, "get_address", return_value="some_peer_id")
    node.started = True

    asyncio.create_task(node.connect())
    await asyncio.sleep(1)

    node.started = False
    await asyncio.sleep(1)

    assert node.peer_id == "some_peer_id"


@pytest.mark.asyncio
async def test_connect_when_node_not_available(mocker):
    node = HOPRNode("some_url", "some_api_key")

    mocker.patch.object(node.api, "get_address", return_value=None)
    node.started = True

    asyncio.create_task(node.connect())
    await asyncio.sleep(1)

    node.started = False
    await asyncio.sleep(1)

    assert node.peer_id is None


# def test_adding_peers_while_pinging() -> None:
#     """
#     Changing the 'peers' set while pinging should not break.
#     NOTE: Incoherence here with the test dealing with Exception: here nothing should
#     break even if the peer accessed via the API is not existing (should raise), while
#     in the other tests exception are raised and the node is stopped.
#     """

#     class MockHoprNode(HOPRNode):
#         def __init__(self, url: str, key: str):
#             """
#             Patched constructor: connected and started
#             """
#             super().__init__(url, key)
#             self.started = True

#         async def connect(self, address: str = "hopr"):
#             self.peer_id = "testing_peer_id"
#             while self.started:
#                 await asyncio.sleep(5)

#         async def gather_peers(self):
#             """
#             Patched to discover one additional peer every couple of seconds
#             """
#             while self.started:
#                 await asyncio.sleep(1)
#                 peer = f"peer_{len(self.peers)}"
#                 self.peers.add(peer)

#     node = MockHoprNode("some_url", "some_key")
#     loop = asyncio.new_event_loop()

#     loop.call_later(2, lambda: node.stop())
#     loop.run_until_complete(node.start())
#     loop.close()

# @pytest.mark.asyncio
# async def test_ping_peers_adds_new_peer_to_latency():
#     """
#     Test that a new entry gets created for a new peer in the latency dictionary
#     with an empty list.
#     """

#     async def _wait_for_latency_to_match_peers():
#         while len(node.latency) < len(node.peers):
#             await asyncio.sleep(0.2)

#     node = HOPRNode("some_url", "some_api_key")
#     node.peer_id = "some_peer_id"
#     node.peers = {"some_other_peer_id_1", "some_other_peer_id_2"}
#     node.latency = {"some_other_peer_id_1": [10, 15]}

#     node.started = True
#     task = asyncio.create_task(node.ping_peers())

#     try:
#         await asyncio.wait_for(_wait_for_latency_to_match_peers(), timeout=15)
#     except asyncio.TimeoutError:
#         raise AssertionError("Timed out waiting for latency to match peers")

#     finally:
#         node.started = False
#         await asyncio.sleep(5)

#         assert "some_other_peer_id_1" in node.latency.keys()
#         assert "some_other_peer_id_2" in node.latency.keys()
#         assert len(node.latency["some_other_peer_id_2"]) == 1  # initialized with np.nan

#         await asyncio.gather(task)
