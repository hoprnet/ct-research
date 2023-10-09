import pytest
from unittest import mock
from unittest.mock import MagicMock  # noqa F401
from unittest.mock import patch  # noqa F401

from economic_handler.utils_econhandler import (
    exclude_elements,
    reward_probability,
    save_dict_to_csv,
    allow_many_node_per_safe,  # noqa F401
    merge_topology_database_subgraph,
)
from economic_handler.peer import Peer
from economic_handler.economic_model import EconomicModel


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
                "value": 1,
                "comment": "budget for the given distribution period",
            },
            "budget_period": {
                "value": 2628000,  # Month in seconds
                "comment": "budget period in seconds",
            },
            "s": {
                "value": 0.25,
                "comment": "split ratio between automated and airdrop mode",
            },
            "dist_freq": {
                "value": 2,
                "comment": "distribution frequency of rewards via the automatic distribution",
            },
            "ticket_price": {
                "value": 0.01,
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
def expected_merge_result() -> list[Peer]:
    """
    Mock the output of the merge_topology_database_subgraph method
    """
    peer_1 = Peer("peer_id_1", "address_1", 5)
    peer_1.node_ids = ["node_1", "node_3"]
    peer_1.safe_address = "safe_1"
    peer_1.safe_balance = 10

    peer_2 = Peer("peer_id_2", "address_2", 2)
    peer_2.node_ids = ["node_1", "node_2", "node_4"]
    peer_2.safe_address = "safe_2"
    peer_2.safe_balance = 8

    peer_3 = Peer("peer_id_3", "address_3", 4)
    peer_3.node_ids = ["node_1", "node_2", "node_4"]
    peer_3.safe_address = "safe_2"
    peer_3.safe_balance = 8

    return [peer_1, peer_2, peer_3]


@pytest.fixture
def mock_rpch_nodes_blacklist():
    return ["peer_id_2", "peer_id_3"]


def test_merge_topology_database_subgraph(merge_data):
    """
    Test whether merge_topology_metricdb_subgraph merges the data as expected.
    """
    unique_peerId_address = merge_data[0]
    new_metrics_dict = merge_data[1]
    new_subgraph_dict = merge_data[2]

    peers = merge_topology_database_subgraph(
        unique_peerId_address, new_metrics_dict, new_subgraph_dict
    )

    # check that all keys are present and check the calculation
    for peer in peers:
        assert peer.complete
        assert peer.total_balance == peer.safe_balance + peer.channel_balance


def test_allow_many_node_per_safe(expected_merge_result: list[Peer]):
    """
    Test whether the method correctly splits the stake.
    """
    allow_many_node_per_safe(expected_merge_result)

    # Assert calculation and count of safe addresses works
    peer_1, peer_2, peer_3 = expected_merge_result

    assert peer_1.split_stake == peer_1.total_balance / peer_1.safe_address_count
    assert peer_2.safe_address_count == 2
    assert peer_3.split_stake == 8


def test_exclude_elements(mock_rpch_nodes_blacklist, expected_merge_result: list[Peer]):
    """
    Test whether the function returns the updated dictionary without the rpch
    node keys. Test that the correct amount of peer_ids gets filtered out and
    that the correct peer_ids are filtered out.
    """
    expected_peer_ids = ["peer_id_1"]

    exclude_elements(expected_merge_result, mock_rpch_nodes_blacklist)

    remaining_peer_ids = [peer.id for peer in expected_merge_result]
    assert len(expected_merge_result) == len(expected_peer_ids)
    assert all(peer_id in remaining_peer_ids for peer_id in expected_peer_ids)


def test_reward_probability(mocked_model_parameters, expected_merge_result: list[Peer]):
    """
    Test whether the sum of probabilities is "close" to 1 due to
    floating-point precision and test that the calculations work.
    """

    model = EconomicModel.from_dictionary(mocked_model_parameters)

    for peer in expected_merge_result:
        peer.economic_model = model

    reward_probability(expected_merge_result)

    sum_probabilities = sum(peer.reward_probability for peer in expected_merge_result)

    # assert that sum is close to 1 due to floating-point precision
    assert pytest.approx(sum_probabilities, abs=1e-6) == 1.0

    # assert that the stake transformtion works correctly
    assert round(expected_merge_result[0].transformed_stake, 4) == 14.4142

    # assert that the stake treshold applies correctly
    assert (
        expected_merge_result[2].transformed_stake
        == expected_merge_result[2].split_stake
    )


def test_compute_expected_reward(
    mocked_model_parameters, expected_merge_result: list[Peer]
):
    """
    Test whether the compute_expected_reward method generates
    the required values and whether the budget gets split correctly.
    """

    model = EconomicModel.from_dictionary(mocked_model_parameters)

    for peer in expected_merge_result:
        peer.economic_model = model

    reward_probability(expected_merge_result)

    # Assert reward calculation
    assert round(expected_merge_result[0].expected_reward, 2) == 0.4

    # Assert APY calculation
    assert round(expected_merge_result[0].apy_percentage) == 32

    # Assert distribution frequency
    assert round(expected_merge_result[0].protocol_reward_per_distribution, 4) == 0.0495

    # Assert job creation
    assert expected_merge_result[0].message_count_for_reward == 5

    for peer in expected_merge_result:
        # Assert that all keys are present
        assert peer.expected_reward is not None
        assert peer.protocol_reward is not None
        assert peer.airdrop_reward is not None
        assert peer.apy_percentage is not None
        assert peer.protocol_reward_per_distribution is not None
        assert peer.economic_model.budget.ticket_price is not None
        assert peer.economic_model.budget.winning_probability is not None
        assert peer.message_count_for_reward is not None

        # Assert that the reward split works correctly
        assert (
            peer.expected_reward
            == peer.protocol_reward + peer.airdrop_reward
            == peer.reward_probability * peer.economic_model.budget.budget
        )


def test_gcp_save_expected_reward_csv_success(
    expected_merge_result: list[Peer], mocked_model_parameters
):
    """
    Test whether the save_expected_reward_csv function returns the confirmation
    message in case of no errors.
    """

    model = EconomicModel.from_dictionary(mocked_model_parameters)

    for peer in expected_merge_result:
        peer.economic_model = model

    reward_probability(expected_merge_result)

    result = save_dict_to_csv(expected_merge_result, foldername="expected_rewards")

    assert result is True


def test_save_expected_reward_csv_OSError_writing_csv(
    expected_merge_result: list[Peer],
):
    """
    Test whether an OSError gets triggered when something goes wrong
    while writing the csv file.
    """
    pass
    # check that the test is still needed


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
