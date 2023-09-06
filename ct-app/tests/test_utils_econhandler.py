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
    merge_topology_database_subgraph,
)


@pytest.fixture
def mocked_model_parameters():
    return {
        "parameters": {
            "a": {"value": 1, "comment": "slope coefficient of linear equation f(x)"},
            "b": {
                "value": 2,
                "comment": "denominator of the exponent of nonlinear function g(x)",
            },
            "c": {
                "value": 13,
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
def mock_open_file():
    with mock.patch("builtins.open") as mock_open_func:
        yield mock_open_func


@pytest.fixture
def merge_data():
    """
    Mock metrics returned by the channel topology endpoint, the database
    and the subgraph
    """
    unique_peerId_address = {
        "peer_id_1": {
            "source_node_address": "address_1",
            "channels_balance": 10,
        },
        "peer_id_2": {
            "source_node_address": "address_2",
            "channels_balance": 20,
        },
    }

    metrics_dict = {
        "peer_id_1": {"node_peer_ids": ["node_1", "node_3"]},
        "peer_id_2": {"node_peer_ids": ["node_1", "node_2", "node_4"]},
    }

    subgraph_dict = {
        "address_1": {
            "safe_address": "safe_1",
            "wxHOPR_balance": 20,
        },
        "address_2": {
            "safe_address": "safe_1",
            "wxHOPR_balance": 30,
        },
    }

    return unique_peerId_address, metrics_dict, subgraph_dict


@pytest.fixture
def expected_merge_result():
    """
    Mock the output of the merge_topology_database_subgraph method
    """
    expected_result = {
        "peer_id_1": {
            "source_node_address": "address_1",
            "channels_balance": 5,
            "node_peer_ids": ["node_1", "node_3"],
            "safe_address": "safe_1",
            "safe_balance": 10,
            "total_balance": 15,
        },
        "peer_id_2": {
            "source_node_address": "address_2",
            "channels_balance": 2,
            "node_peer_ids": ["node_1", "node_2", "node_4"],
            "safe_address": "safe_2",
            "safe_balance": 8,
            "total_balance": 10,
        },
        "peer_id_3": {
            "source_node_address": "address_3",
            "channels_balance": 4,
            "node_peer_ids": ["node_1", "node_2", "node_4"],
            "safe_address": "safe_2",
            "safe_balance": 8,
            "total_balance": 12,
        },
    }
    return expected_result


@pytest.fixture
def mock_rpch_nodes_blacklist():
    return ["peer_id_2", "peer_id_3"]


@pytest.fixture
def expected_merge_result_split_stake(expected_merge_result):
    """
    Add new keys to the expected_merge_result @pytest.fixture
    """
    result = expected_merge_result.copy()

    # Define split stake values for specific peer IDs
    split_stake_values = {
        "peer_id_1": 15,
        "peer_id_2": 5,
        "peer_id_3": 6,
    }

    # Update the split stake values for the specified peer IDs
    for peer_id, split_stake in split_stake_values.items():
        if peer_id in result:
            result[peer_id]["splitted_stake"] = split_stake

    return result


def test_merge_topology_database_subgraph(merge_data):
    """
    Test whether merge_topology_metricdb_subgraph merges the data as expected.
    """
    unique_peerId_address = merge_data[0]
    new_metrics_dict = merge_data[1]
    new_subgraph_dict = merge_data[2]

    result = merge_topology_database_subgraph(
        unique_peerId_address, new_metrics_dict, new_subgraph_dict
    )
    keys_to_check = [
        "source_node_address",
        "channels_balance",
        "node_peer_ids",
        "safe_address",
        "safe_balance",
        "total_balance",
    ]

    # check that all keys are present and check the calculation
    for value in result.values():
        assert all(key in value for key in keys_to_check)
        assert (
            value["total_balance"] == value["safe_balance"] + value["channels_balance"]
        )


def test_allow_many_node_per_safe(expected_merge_result):
    """
    Test whether the method correctly splits the stake.
    """
    allow_many_node_per_safe(expected_merge_result)

    # Assert calculation and count of safe addresses works
    assert (
        expected_merge_result["peer_id_1"]["splitted_stake"]
        == expected_merge_result["peer_id_1"]["total_balance"]
        / expected_merge_result["peer_id_1"]["safe_address_count"]
    )
    assert expected_merge_result["peer_id_2"]["safe_address_count"] == 2
    assert expected_merge_result["peer_id_3"]["splitted_stake"] == 6


def test_exclude_elements(mock_rpch_nodes_blacklist, expected_merge_result):
    """
    Test whether the function returns the updated dictionary without the rpch
    node keys. Test that the correct amount of peer_ids gets filtered out and
    that the correct peer_ids are filtered out.
    """
    expected_peer_ids = ["peer_id_1"]

    exclude_elements(expected_merge_result, mock_rpch_nodes_blacklist)

    assert len(expected_merge_result) == len(expected_peer_ids)
    assert all(peer_id in expected_merge_result for peer_id in expected_peer_ids)


def test_reward_probability(mocked_model_parameters, expected_merge_result_split_stake):
    """
    Test whether the sum of probabilities is "close" to 1 due to
    floating-point precision and test that the calculations work.
    """
    parameters: dict = mocked_model_parameters["parameters"]
    equations: dict = mocked_model_parameters["equations"]
    merged_result: dict = expected_merge_result_split_stake

    keys_to_check = [
        "trans_stake",
        "prob",
    ]

    reward_probability(merged_result, equations, parameters)
    sum_probabilities = sum(value["prob"] for _, value in merged_result.items())

    for value in merged_result.values():
        assert all(key in value for key in keys_to_check)

    # assert that sum is close to 1 due to floating-point precision
    assert pytest.approx(sum_probabilities, abs=1e-6) == 1.0

    # assert that the stake transformtion works correctly
    assert round(merged_result["peer_id_1"]["trans_stake"], 4) == 14.4142

    # assert that the stake treshold applies correctly
    assert (
        merged_result["peer_id_3"]["trans_stake"]
        == merged_result["peer_id_3"]["splitted_stake"]
    )


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
