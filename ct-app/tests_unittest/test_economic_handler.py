# import json
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ["PARAMETER_FILE"] = "parameters.json"

# PATCH THE DECORATOR HERE
patch(
    "economic_handler.utils_econhandler.determine_delay_from_parameters", return_value=5
).start()


from economic_handler.economic_handler import EconomicHandler  # noqa: E402


@pytest.fixture
def mock_node_for_test_start(mocker):
    """
    Create a mock for each coroutine that should be executed.
    """
    mocker.patch.object(EconomicHandler, "connect", return_value=None)
    mocker.patch.object(EconomicHandler, "host_available", return_value=None)
    mocker.patch.object(EconomicHandler, "get_database_metrics", return_value=None)
    mocker.patch.object(
        EconomicHandler, "get_topology_links_with_balance", return_value=None
    )
    # mocker.patch.object(EconomicHandler, "get_rpch_nodes", return_value=None)
    mocker.patch.object(EconomicHandler, "get_ct_nodes", return_value=None)
    mocker.patch.object(EconomicHandler, "get_subgraph_data", return_value=None)
    mocker.patch.object(EconomicHandler, "close_incoming_channels", return_value=None)
    mocker.patch.object(EconomicHandler, "apply_economic_model", return_value=None)
    mocker.patch.object(EconomicHandler, "reward_peers", return_value=None)

    return EconomicHandler(
        "some_url", "some_api_key", "some_rpch_endpoint", "some_subgraph_url"
    )


@pytest.mark.asyncio
async def test_start(mock_node_for_test_start: EconomicHandler):
    """
    Test whether all coroutines were called with the expected arguments.
    """
    node = mock_node_for_test_start
    await node.start()

    assert node.connect.called
    assert node.host_available.called
    assert node.get_database_metrics.called
    assert node.get_topology_links_with_balance.called
    # assert node.get_rpch_nodes.called
    assert node.get_ct_nodes.called
    assert node.get_subgraph_data.called
    # assert node.close_incoming_channels.called
    assert node.apply_economic_model.called
    assert node.reward_peers.called

    assert len(node.tasks) == 8
    assert node.started

    node.started = False


def test_stop():
    """
    Test whether the stop method cancels the tasks and updates the 'started' attribute.
    """
    mocked_task = MagicMock()
    node = EconomicHandler(
        "some_url", "some_api_key", "some_rpch_endpoint", "some_subgraph_url"
    )
    node.tasks = {mocked_task}

    node.stop()

    assert not node.started
    mocked_task.cancel.assert_called_once()
    assert node.tasks == set()