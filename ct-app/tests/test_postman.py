import os
import time

import pytest

os.environ["TASK_NAME"] = "foo_task"
os.environ["NODE_ADDRESS"] = "0x1234567890"
os.environ["PROJECT_NAME"] = "foo_project"
os.environ["CELERY_BROKER_URL"] = "foo_broker_url"
os.environ["TIMEOUT"] = "5"
os.environ["API_HOST"] = "foo_api_host"
os.environ["API_KEY"] = "foo_api_key"


import postman as pm  # noqa: E402


def test_loop_through():
    """Test that the loop_through methods actually loop back to the beginning of the
    list"""

    node_list = ["node1", "node2", "node3"]

    _, node_index = pm.loop_through_nodes(node_list, 0)
    assert node_index == 1

    _, node_index = pm.loop_through_nodes(node_list, 1)
    assert node_index == 2

    _, node_index = pm.loop_through_nodes(node_list, 2)
    assert node_index == 0


@pytest.mark.asyncio
async def test_async_send_1_hop_message_hit_timeout():
    """
    Test that the async_send_1_hop_message method returns a TIMEOUT status when the last
    known timestamp is older than 5 seconds (set for testing).
    """
    os.environ["TIMEOUT"] = "5"

    status, fb_status = await pm.async_send_1_hop_message(
        peer_id="foo_peer_id",
        expected_count=10,
        node_list=["node1", "node2", "node3"],
        node_index=0,
        timestamp=time.time() - 10,
    )

    assert status == pm.TaskStatus.TIMEOUT
    assert fb_status == pm.TaskStatus.DEFAULT


@pytest.mark.asyncio
async def test_async_send_1_hop_message_hit_retried(mocker):
    """
    Test that the async_send_1_hop_message method returns a RETRIED status when the
    targeted node is not reachable."""
    mocker.patch("postman.postman_tasks.HoprdAPIHelper.get_address", return_value=None)

    status, fb_status = await pm.async_send_1_hop_message(
        peer_id="foo_peer_id",
        expected_count=10,
        node_list=["node1", "node2", "node3"],
        node_index=0,
        timestamp=time.time(),
    )

    assert status == pm.TaskStatus.RETRIED
    assert fb_status == pm.TaskStatus.FAILED


@pytest.mark.asyncio
async def test_async_send_1_hop_message_hit_splitted(mocker):
    """
    Test that the async_send_1_hop_message method returns a SPLITTED status when the
    targeted node is reachable but messages could not be sent."""
    mocker.patch(
        "postman.postman_tasks.HoprdAPIHelper.get_address", return_value="foo_address"
    )
    mocker.patch(
        "postman.postman_tasks.HoprdAPIHelper.send_message", return_value=False
    )

    status, fb_status = await pm.async_send_1_hop_message(
        peer_id="foo_peer_id",
        expected_count=10,
        node_list=["node1", "node2", "node3"],
        node_index=0,
        timestamp=time.time(),
    )

    assert status == pm.TaskStatus.SPLITTED
    assert fb_status == pm.TaskStatus.FAILED


@pytest.mark.asyncio
async def test_async_send_1_hop_message_hit_success(mocker):
    """
    Test that the async_send_1_hop_message method returns a SUCCESS status when the
    targeted node is reachable and messages are sent."""
    mocker.patch(
        "postman.postman_tasks.HoprdAPIHelper.get_address", return_value="foo_address"
    )
    mocker.patch("postman.postman_tasks.HoprdAPIHelper.send_message", return_value=True)

    status, fb_status = await pm.async_send_1_hop_message(
        peer_id="foo_peer_id",
        expected_count=10,
        node_list=["node1", "node2", "node3"],
        node_index=0,
        timestamp=time.time(),
    )

    assert status == pm.TaskStatus.SUCCESS
    assert fb_status == pm.TaskStatus.FAILED
