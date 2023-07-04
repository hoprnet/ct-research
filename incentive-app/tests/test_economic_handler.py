import json
import pytest
from unittest import mock
from economic_handler.economic_handler import EconomicHandler


@pytest.fixture(scope="module", autouse=True)
def file_contents():
    return {
        "parameters": {
            "first_parameter": {
                "value": 1,
                "comment": "some comment",
            },
            "second_parameter": {
                "value": 3,
                "comment": "some comment",
            },
            "third_parameter": {
                "value": 3,
                "comment": "some comment",
            },
            "fourth_parameter": {
                "value": -1,
                "comment": "some comment",
            },
        },
        "equations": {
            "first_equation": {
                "formula": "some formula",
                "condition": "some condition",
            },
            "second_equation": {
                "formula": "some other formula",
                "condition": "some other condition",
            },
        },
        "budget": {"value": 100, "comment": "some comment"},
    }


@pytest.fixture
def mock_open_file():
    with mock.patch("builtins.open") as mock_open_func:
        yield mock_open_func


@pytest.mark.asyncio
async def test_read_parameters_and_equations(mock_open_file, file_contents):
    """
    Test whether parameters, equations, and budget are correctly returned
    as a dictionary
    """
    mock_file = mock_open_file.return_value.__enter__.return_value
    mock_file.read.return_value = json.dumps(file_contents)

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(mock_file)

    assert isinstance(result[1], dict)
    assert isinstance(result[2], dict)
    assert isinstance(result[3], dict)


@pytest.mark.asyncio
async def test_read_parameters_and_equations_file_not_found():
    """
    Test whether an empty dictionary gets returned in case of a FileNotFoundError.
    """
    file_name = "non_existent_file.json"
    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(file_name)

    assert result == ("params", {}, {}, {})


@pytest.mark.asyncio
async def test_read_parameters_and_equations_check_values(
    mock_open_file, file_contents
):
    """
    Test whether an empty dictionary gets returned in case of a ValidationError.
    """
    mock_file = mock_open_file.return_value.__enter__.return_value
    mock_file.read.return_value = json.dumps(file_contents)

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = await node.read_parameters_and_equations(mock_file)

    assert result == ("params", {}, {}, {})

    
@pytest.fixture
def merge_data():
    """
    Mock metrics returned by the channel topology endpoint, the database
    and the subgraph
    """
    unique_peerId_address = {
        "peer_id_1": "safe_1",
        "peer_id_2": "safe_2",
        "peer_id_3": "safe_3",
        "peer_id_4": "safe_4",
        "peer_id_5": "safe_5",
    }
    metrics_dict = {
        "peer_id_1": {"netw": ["nw_1", "nw_3"]},
        "peer_id_2": {"netw": ["nw_1", "nw_2", "nw_4"]},
        "peer_id_3": {"netw": ["nw_2", "nw_3", "nw_4"]},
        "peer_id_4": {"netw": ["nw_1", "nw_2", "nw_3"]},
        "peer_id_5": {"netw": ["nw_1", "nw_2", "nw_3", "nw_4"]},
    }
    subgraph_dict = {
        "safe_1": {"stake": 10},
        "safe_2": {"stake": 55},
        "safe_3": {"stake": 23},
        "safe_4": {"stake": 85},
        "safe_5": {"stake": 62},
    }

    return unique_peerId_address, metrics_dict, subgraph_dict


def test_merge_topology_metricdb_subgraph(merge_data):
    """
    Test whether merge_topology_metricdb_subgraph merges the data as expected.
    """
    unique_peerId_address = merge_data[0]
    new_metrics_dict = merge_data[1]
    new_subgraph_dict = merge_data[2]

    expected_result = {
        "peer_id_1": {
            "safe_address": "safe_1",
            "netwatchers": ["nw_1", "nw_3"],
            "stake": 10,
        },
        "peer_id_2": {
            "safe_address": "safe_2",
            "netwatchers": ["nw_1", "nw_2", "nw_4"],
            "stake": 55,
        },
        "peer_id_3": {
            "safe_address": "safe_3",
            "netwatchers": ["nw_2", "nw_3", "nw_4"],
            "stake": 23,
        },
        "peer_id_4": {
            "safe_address": "safe_4",
            "netwatchers": ["nw_1", "nw_2", "nw_3"],
            "stake": 85,
        },
        "peer_id_5": {
            "safe_address": "safe_5",
            "netwatchers": ["nw_1", "nw_2", "nw_3", "nw_4"],
            "stake": 62,
        },
    }

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")
    result = node.merge_topology_metricdb_subgraph(
        unique_peerId_address, new_metrics_dict, new_subgraph_dict
    )

    assert result == ("merged_data", expected_result)


def test_merge_topology_metricdb_subgraph_exception(merge_data):
    """
    Test whether an empty dictionary gets returned in case the exception gets triggered.
    """
    unique_peerId_address = merge_data[0]
    new_metrics_dict = merge_data[1]
    new_subgraph_dict = {}

    node = EconomicHandler("some_url", "some_api_key", "some_rpch_endpoint")

    result = node.merge_topology_metricdb_subgraph(
        unique_peerId_address, new_metrics_dict, new_subgraph_dict
    )

    assert result == ("merged_data", {})
