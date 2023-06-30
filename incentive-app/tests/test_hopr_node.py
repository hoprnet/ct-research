# import asyncio
# import pytest
# from tools import HOPRNode


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


# @pytest.fixture
# def get_mock_node_for_connect():
#     """Fixture that returns a mock instance of a started MockHoprNode
#     with a given peer_id
#     """

#     class MockHoprNode(HOPRNode):
#         def __init__(self, url: str, key: str):
#             super().__init__(url, key)

#         async def start(self):
#             """
#             Starts the tasks of this node
#             """
#             if len(self.tasks) == 0:
#                 self.started = True
#                 self.tasks.add(asyncio.create_task(self.connect()))
#                 await asyncio.gather(*self.tasks)

#     return MockHoprNode("some_url", "some_api_key")


# @pytest.mark.asyncio
# async def test_connect_exception(mocker, event_loop, get_mock_node_for_connect):
#     """
#     Test that peer_id is set to None when the exception gets triggered.
#     """
#     node = get_mock_node_for_connect
#     assert node.peer_id is None
#     mocker.patch.object(node.api, "get_address", side_effect=Exception())

#     event_loop.call_later(2, lambda: node.stop())
#     await node.start()
#     assert node.peer_id is None


# @pytest.mark.asyncio
# async def test_connect_exception_logging(
#     mocker, caplog, event_loop, get_mock_node_for_connect
# ):
#     """
#     Test that the correct log message is logged when an exception occurs
#     during the connect method.
#     """
#     node = get_mock_node_for_connect
#     mocker.patch.object(node.api, "get_address", side_effect=Exception())

#     event_loop.call_later(2, lambda: node.stop())
#     await node.start()
#     assert "Could not connect to" in caplog.text


# @pytest.mark.asyncio
# async def test_connected_property(mocker, event_loop, get_mock_node_for_connect):
#     """
#     Test the `connected' property returns false by default.
#     Test the `connected' property returns true after successful connection.
#     Test the `connected' property returns false by after the node has been stopped.
#     """
#     node = get_mock_node_for_connect
#     assert not node.connected

#     # Mock the HOPRd API to return a JSON response with two peers
#     class MockedResponse:
#         def json(self):
#             return {"hopr": "some_other_peer_id_1"}

#     class MockedHoprdAPI:
#         async def get_address(self, address: str):
#             return "some_other_peer_id_1"

#     node.api = MockedHoprdAPI()

#     # helper function to assert from the event loop
#     def assert_node_connected():
#         assert node.connected

#     event_loop.call_later(0.5, lambda: assert_node_connected())
#     event_loop.call_later(1.0, lambda: node.stop())
#     await node.start()
#     assert not node.connected


# def test_disconnect_method():
#     """
#     Test that the node is disconnected after calling disconnect method
#     Test that the peer_id attribute is set to None after calling disconnect method
#     """
#     node = HOPRNode("some_url", "some_api_key")
#     node.peer_id = "some_peer_id"
#     node.disconnect()
#     assert not node.connected
#     assert node.peer_id is None


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
# async def test_gather_peers_retrieves_peers_from_response():
#     """
#     Test whether gather_peers retrieves the correct list of peers
#     from the JSON response returned by the _req() method.
#     """
#     node = HOPRNode("some_url", "some_api_key")
#     node.peer_id = "some_peer_id"

#     class MockedHoprdAPI:
#         async def peers(self, param, quality):
#             assert quality == 1
#             return ["some_other_peer_id_1", "some_other_peer_id_2"]

#     node.api = MockedHoprdAPI()

#     node.started = True
#     task = asyncio.create_task(node.gather_peers())
#     await asyncio.sleep(1)

#     # avoid infinite while loop by setting node.started = False
#     node.started = False
#     await asyncio.sleep(1)

#     assert "some_other_peer_id_1" in node.peers
#     assert "some_other_peer_id_2" in node.peers
#     await asyncio.gather(task)


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


# @pytest.fixture
# def mock_node_for_test_start(mocker):
#     # create a mock for each coroutine that should be executed
#     mocker.patch.object(HOPRNode, "connect", return_value=None)
#     mocker.patch.object(HOPRNode, "gather_peers", return_value=None)
#     mocker.patch.object(HOPRNode, "ping_peers", return_value=None)
#     mocker.patch.object(HOPRNode, "plot", return_value=None)

#     return HOPRNode("some_url", "some_api_key")


# @pytest.mark.asyncio
# async def test_start(mock_node_for_test_start):
#     """
#     Test whether all coroutines were called with the expected arguments.
#     """
#     node = mock_node_for_test_start
#     await node.start()

#     assert node.connect.called
#     assert node.gather_peers.called
#     assert node.ping_peers.called
#     assert node.plot.called
#     assert len(node.tasks) == 4
#     assert node.started
