import asyncio  # noqa: F401
import pytest  # noqa: F401

from netwatcher import NetWatcher
from tools.hopr_api_helper import HoprdAPIHelper  # noqa: F401


def FakeNetWatcher() -> NetWatcher:
    """Fixture that returns a mock instance of a NetWatcher"""
    return NetWatcher("some_url", "some_key", "some_posturl", 10)


# @pytest.mark.asyncio
# async def test_connect_successful(mocker):
#     """
#     Test that the method connects successfully to the HOPR node and sets the correct
#     peer_id attribute value.
#     """
#     node = FakeNetWatcher()

#     mocker.patch.object(node.api, "get_address", return_value="some_peer_id")

#     node.started = True
#     task = asyncio.create_task(node.connect())
#     await asyncio.sleep(1)

#     # avoid infinite while loop by setting node.started = False
#     assert node.peer_id == "some_peer_id"

#     try:
#         await asyncio.wait_for(task, timeout=2)
#     except asyncio.TimeoutError:
#         print("The task was canceleld due to a timeout")


def test_disconnect_method():
    """
    Test that the node is disconnected after calling disconnect method
    Test that the peer_id attribute is set to None after calling disconnect method
    """
    node = FakeNetWatcher()
    node.peer_id = "some_peer_id"

    node.disconnect()

    assert not node.connected
    assert node.peer_id is None
