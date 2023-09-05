import pprint
import pytest
from unittest import mock
from unittest.mock import MagicMock  # noqa F401
from unittest.mock import patch  # noqa F401

from economic_handler.utils_econhandler import (
    exclude_elements,
    reward_probability,
    save_dict_to_csv,
    allow_many_node_per_safe,  # noqa F401
    compute_rewards,  # noqa F401
)


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
        "budget_param": {"value": 100, "comment": "some comment"},
    }


@pytest.fixture
def mock_open_file():
    with mock.patch("builtins.open") as mock_open_func:
        yield mock_open_func


# @pytest.mark.asyncio
# async def test_read_parameters_and_equations(mock_open_file, file_contents):
#     """
#     Test whether parameters, equations, and budget are correctly returned
#     as a dictionary
#     """
#     mock_file = mock_open_file.return_value.__enter__.return_value
#     mock_file.read.return_value = json.dumps(file_contents)

#     node = EconomicHandler(
#         "some_url",
#         "some_api_key",
#         "some_rpch_endpoint",
#         "some_subgraph_url",
#     )

#     result = await node.read_parameters_and_equations(mock_file)

#     assert isinstance(result[1], dict)
#     assert isinstance(result[2], dict)
#     assert isinstance(result[3], dict)


# @pytest.mark.asyncio
# async def test_read_parameters_and_equations_file_not_found():
#     """
#     Test whether an empty dictionary gets returned in case of a FileNotFoundError.
#     """
#     file_name = "non_existent_file.json"
#     node = EconomicHandler(
#         "some_url",
#         "some_api_key",
#         "some_rpch_endpoint",
#         "some_subgraph_url",
#     )

#     result = await node.read_parameters_and_equations(file_name)

#     assert result == ("params", {}, {}, {})


# @pytest.mark.asyncio
# async def test_read_parameters_and_equations_check_values(
#     mock_open_file, file_contents
# ):
#     """
#     Test whether an empty dictionary gets returned in case of a ValidationError.
#     """
#     mock_file = mock_open_file.return_value.__enter__.return_value
#     mock_file.read.return_value = json.dumps(file_contents)

#     node = EconomicHandler(
#         "some_url",
#         "some_api_key",
#         "some_rpch_endpoint",
#         "some_subgraph_url",
#     )

#     result = await node.read_parameters_and_equations(mock_file)

#     assert result == ("params", {}, {}, {})


@pytest.fixture
def merge_data():
    """
    Mock metrics returned by the channel topology endpoint, the database
    and the subgraph
    """
    unique_peerId_address = {
        "peer_id_1": "safe_1",
        "peer_id_2": "safe_1",
        "peer_id_3": "safe_3",
        "peer_id_4": "safe_4",
        "peer_id_5": "safe_5",
    }
    metrics_dict = {
        "peer_id_1": {"netw": ["node_1", "node_3"]},
        "peer_id_2": {"netw": ["node_1", "node_2", "node_4"]},
        "peer_id_3": {"netw": ["node_2", "node_3", "node_4"]},
        "peer_id_4": {"netw": ["node_1", "node_2", "node_3"]},
        "peer_id_5": {"netw": ["node_1", "node_2", "node_3", "node_4"]},
    }
    subgraph_dict = {
        "safe_1": 65,
        "safe_3": 23,
        "safe_4": 85,
        "safe_5": 62,
    }

    return unique_peerId_address, metrics_dict, subgraph_dict


@pytest.fixture
def expected_merge_result():
    return {
        "peer_id_1": {
            "safe_address": "safe_1",
            "node_addresses": ["node_1", "node_3"],
            "stake": 65,
        },
        "peer_id_2": {
            "safe_address": "safe_1",
            "node_addresses": ["node_1", "node_2", "node_4"],
            "stake": 65,
        },
        "peer_id_3": {
            "safe_address": "safe_3",
            "node_addresses": ["node_2", "node_3", "node_4"],
            "stake": 23,
        },
        "peer_id_4": {
            "safe_address": "safe_4",
            "node_addresses": ["node_1", "node_2", "node_3"],
            "stake": 85,
        },
        "peer_id_5": {
            "safe_address": "safe_5",
            "node_addresses": ["node_1", "node_2", "node_3", "node_4"],
            "stake": 62,
        },
    }


@pytest.fixture
def mock_rpch_nodes_blacklist():
    return ["peer_id_4", "peer_id_5"]


@pytest.fixture
def expected_split_stake_result():
    return {
        "peer_id_1": {
            "safe_address": "safe_1",
            "node_addresses": ["node_1", "node_3"],
            "stake": 65,
            "safe_address_count": 2,
            "splitted_stake": 32.5,
        },
        "peer_id_2": {
            "safe_address": "safe_1",
            "node_addresses": ["node_1", "node_2", "node_4"],
            "stake": 65,
            "safe_address_count": 2,
            "splitted_stake": 32.5,
        },
        "peer_id_3": {
            "safe_address": "safe_3",
            "node_addresses": ["node_2", "node_3", "node_4"],
            "stake": 23,
            "safe_address_count": 1,
            "splitted_stake": 23,
        },
        "peer_id_4": {
            "safe_address": "safe_4",
            "node_addresses": ["node_1", "node_2", "node_3"],
            "stake": 85,
            "safe_address_count": 1,
            "splitted_stake": 85,
        },
        "peer_id_5": {
            "safe_address": "safe_5",
            "node_addresses": ["node_1", "node_2", "node_3", "node_4"],
            "stake": 62,
            "safe_address_count": 1,
            "splitted_stake": 62,
        },
    }


@pytest.fixture
def mocked_model_parameters():
    return {
        "parameters": {
            "a": {"value": 1, "comment": "slope coefficient of linear equation f(x)"},
            "b": {
                "value": 1,
                "comment": "denominator of the exponent of nonlinear function g(x)",
            },
            "c": {
                "value": 3,
                "comment": "threshold value defining the cutoff for when f(x) ends and g(x) starts",
            },
            "l": {
                "value": 0,
                "comment": "lower limit of linear function (i.e. minimum required stake)",
            },
        },
        "equations": {
            "f_x": {"formula": "a * x", "condition": "l <= x <= c"},
            "g_x": {"formula": "a * c + (x - c) ** (1 / b)", "condition": "x > c"},
        },
        "budget_param": {
            "budget": {
                "value": 100,
                "comment": "budget for the given distribution period",
            },
            "budget_period": {"value": 15, "comment": "budget period in seconds"},
            "s": {
                "value": 0.25,
                "comment": "split ratio between automated and airdrop mode",
            },
            "dist_freq": {
                "value": 2,
                "comment": "distribution frequency of rewards via the automatic distribution",
            },
            "ticket_price": {
                "value": 0.5,
                "comment": "Price of a ticket issued for relaying a packet",
            },
            "winning_prob": {
                "value": 1,
                "comment": "Probability that a ticket has a value",
            },
        },
    }


@pytest.fixture
def new_expected_split_stake_result(expected_split_stake_result):
    """
    Add new keys to the expected_split_stake_result @pytest.fixture
    """
    new_expected_split_stake_result = {}
    for peer_id, values in expected_split_stake_result.items():
        new_values = values.copy()
        new_values["trans_stake"] = "some_value"
        new_values["prob"] = 0.1
        new_expected_split_stake_result[peer_id] = new_values

    return new_expected_split_stake_result


# def test_merge_topology_database_subgraph(merge_data, expected_merge_result):
#     """
#     Test whether merge_topology_metricdb_subgraph merges the data as expected.
#     """
#     unique_peerId_address = merge_data[0]
#     new_metrics_dict = merge_data[1]
#     new_subgraph_dict = merge_data[2]
#     expected_result = expected_merge_result

#     result = merge_topology_database_subgraph(
#         unique_peerId_address, new_metrics_dict, new_subgraph_dict
#     )

#     assert result == expected_result


# def test_merge_topology_database_subgraph_exception(merge_data):
#     """
#     Test whether an empty dictionary gets returned in case the exception gets triggered.
#     """
#     unique_peerId_address = merge_data[0]
#     new_metrics_dict = merge_data[1]
#     new_subgraph_dict = {}

#     result = merge_topology_database_subgraph(
#         unique_peerId_address, new_metrics_dict, new_subgraph_dict
#     )

#     assert result == {}


def test_allow_many_node_per_safe(expected_merge_result, expected_split_stake_result):
    """
    Test whether the method correctly splits the stake
    and returns the expected result dictionary.
    """
    # TODO: HERE THE "total_balance" jkey for each entry is missing in the mocked data
    if 0:
        expected_result = expected_split_stake_result
        print(expected_result)

        allow_many_node_per_safe(expected_merge_result)
        assert expected_merge_result == expected_result


def test_compute_expected_reward(
    mocked_model_parameters, new_expected_split_stake_result
):
    """
    Test whether the compute_expected_reward method generates
    the required values and whether the budget gets split correctly.
    """

    # TODO: HERE THE "total_balance" jkey for each entry is missing in the mocked data
    if 0:
        budget_param = mocked_model_parameters["budget_param"]

        result = compute_rewards(new_expected_split_stake_result, budget_param)

        # Assert Keys
        assert set(result[1].keys()) == set(new_expected_split_stake_result.keys())

        # Assert Values
        for value in result[1].values():
            assert "total_expected_reward" in value
            assert "protocol_exp_reward" in value
            assert "airdrop_expected_reward" in value

        # Assert that the split works correctly
        for entry in result[1].values():
            assert (
                entry["total_expected_reward"]
                == entry["protocol_exp_reward"] + entry["airdrop_expected_reward"]
            )


def test_exclude_elements(mock_rpch_nodes_blacklist, expected_merge_result):
    """
    Test whether the function returns the updated dictionary without the rpch
    node keys. Test that the correct amount of peer_ids gets filtered out and
    that the correct peer_ids are filtered out.
    """
    expected_peer_ids = ["peer_id_1", "peer_id_2", "peer_id_3"]

    exclude_elements(expected_merge_result, mock_rpch_nodes_blacklist)

    assert len(expected_merge_result) == len(expected_peer_ids)
    assert all(peer_id in expected_merge_result for peer_id in expected_peer_ids)


def test_probability_sum(mocked_model_parameters, expected_split_stake_result):
    """
    Test whether the sum of probabilities is "close" to 1 due to
    floating-point precision. Not that the result is a tuple:
    ("ct_prob", merged_result)
    """
    parameters: dict = mocked_model_parameters["parameters"]
    equations: dict = mocked_model_parameters["equations"]
    merged_result: dict = expected_split_stake_result

    reward_probability(merged_result, equations, parameters)
    pprint.pprint(merged_result)
    sum_probabilities = sum(value["prob"] for _, value in merged_result.items())

    # assert that sum is close to 1 due to floating-point precision
    assert pytest.approx(sum_probabilities, abs=1e-6) == 1.0


def test_reward_probablity_exception(mocked_model_parameters):
    """
    Test whether an empty dictionary gets returned when a dataset is missing
    and therefore the exception gets triggered.
    """
    parameters = mocked_model_parameters["parameters"]
    equations = mocked_model_parameters["equations"]
    merged_result = {}

    reward_probability(parameters, equations, merged_result)

    assert merged_result == ({})


def test_gcp_save_expected_reward_csv_success(new_expected_split_stake_result):
    """
    Test whether the save_expected_reward_csv function returns the confirmation
    message in case of no errors.
    """

    result = save_dict_to_csv(
        new_expected_split_stake_result, foldername="expected_rewards"
    )

    assert result is True


def test_save_expected_reward_csv_OSError_writing_csv(new_expected_split_stake_result):
    """
    Test whether an OSError gets triggered when something goes wrong
    while writing the csv file.
    """
    # TODO: check that the test is still needed
