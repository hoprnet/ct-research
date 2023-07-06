import numpy as np
from aggregator import utils


def test_dict_to_array():
    """
    Test that the dict_to_array method works correctly.
    """
    input_dict = {
        "pod_id": {"peer": 1, "peer2": 2},
        "pod_id2": {"peer": 10, "peer2": 2},
    }

    nw_ids = ["pod_id", "pod_id2"]
    peer_ids = ["peer", "peer2"]

    expected_result = np.array([[1, 2], [10, 2]])
    result = utils.dict_to_array(input_dict, nw_ids, peer_ids)

    assert np.array_equal(result, expected_result)


def test_nw_list_from_dict():
    """
    Test that the get_nw_list_from_dict method works correctly.
    """
    input_dict = {"pod_id": {"peer": 1, "peer2": 2}}

    expected_result = ["pod_id"]
    result = utils.get_nw_list_from_dict(input_dict)

    assert result == expected_result


def test_nw_list_from_dict_multiple():
    """
    Test that the get_nw_list_from_dict method works correctly.
    """
    input_dict = {
        "pod_id": {"peer": 1, "peer2": 2},
        "pod_id2": {"peer": 10, "peer2": 2},
    }

    expected_result = ["pod_id", "pod_id2"]
    result = utils.get_nw_list_from_dict(input_dict)

    assert result == expected_result


def test_peer_list_from_dict():
    """
    Test that the get_peer_list_from_dict method works correctly.
    """
    input_dict = {"pod_id": {"peer3": 1, "peer": 2}}

    expected_result = ["peer3", "peer"]
    result = utils.get_peer_list_from_dict(input_dict)

    assert result == expected_result


def test_peer_list_from_dict_multiple():
    """
    Test that the get_peer_list_from_dict method works correctly.
    """
    input_dict = {
        "pod_id": {"peer6": 1, "peer2": 2},
        "pod_id2": {"peer3": 10, "peer2": 2},
    }

    expected_result = ["peer6", "peer2", "peer3"]
    result = utils.get_peer_list_from_dict(input_dict)

    assert result == expected_result


def test_array_to_db_list():
    """
    Test that the array_to_db_list method works correctly.
    """
    input_array = np.array([[1, 2]])
    nw_ids = ["pod_0"]
    peer_ids = ["peer_0", "peer_1"]

    matchs = utils.multiple_round_nw_peer_match(input_array, max_iter=3)

    expected_result = [("peer_0", ["pod_0"], [1]), ("peer_1", ["pod_0"], [2])]
    result = utils.array_to_db_list(input_array, matchs, nw_ids, peer_ids)

    assert result == expected_result


def test_remove_matchs():
    """
    Test that the remove_matchs method works correctly.
    """
    input_array = np.array([[1, 2], [5, 1]])
    expected_result = np.array([[0, 2], [5, 0]])

    matchs = utils.one_round_nw_peer_match(input_array)
    result = utils.remove_matchs(input_array, matchs)

    assert np.array_equal(result, expected_result)


def test_remove_matchs_multiple():
    """
    Test that the remove_matchs method works correctly.
    """
    input_array = np.array([[1, 2], [5, 1], [1, 3]])
    expected_result = np.array([[0, 0], [5, 0], [0, 3]])

    matchs = utils.multiple_round_nw_peer_match(input_array, max_iter=2)
    result = utils.remove_matchs(input_array, matchs)

    assert np.array_equal(result, expected_result)


def test_remove_matchs_all():
    """
    Test that the remove_matchs method works correctly.
    """
    input_array = np.array([[1, 2], [5, 1], [1, 3]])
    expected_result = np.array([[0, 0], [0, 0], [0, 0]])

    matchs = utils.multiple_round_nw_peer_match(input_array)
    result = utils.remove_matchs(input_array, matchs)

    assert np.array_equal(result, expected_result)


def test_merge_matchs_single():
    """
    Test that the merge_matchs method works correctly.
    """
    input_array = np.array([[1, 2], [5, 1], [1, 3]])
    expected_result = {0: [0], 1: [1]}

    matchs = utils.one_round_nw_peer_match(input_array)
    result = utils.merge_matchs([matchs])

    assert result == expected_result


def test_merge_matchs_multiple():
    """
    Test that the merge_matchs method works correctly.
    """
    input_array = np.array([[1, 2], [5, 1], [1, 3]])
    expected_result = {0: [0, 2], 1: [1, 0]}

    match1 = utils.one_round_nw_peer_match(input_array)
    input_array = utils.remove_matchs(input_array, match1)
    match2 = utils.one_round_nw_peer_match(input_array)

    result = utils.merge_matchs([match1, match2])

    assert result == expected_result


def test_one_round_nw_peer_match():
    """
    Test that the one_round_nw_peer_match method works correctly.
    """
    input_array = np.array([[10, 13, 4], [51, 12, 53], [4, 12, 41]])
    expected_result = {0: 2, 1: 1, 2: 0}

    result = utils.one_round_nw_peer_match(input_array)

    assert result == expected_result
