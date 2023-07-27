# enum class with auto numbering
import copy

import numpy as np


def one_round_node_peer_match(input_array: np.ndarray) -> dict:
    """
    This method implements the pairing between nodes and peers for one round.
    At the end of the execution of this method, each peer will be paired with one
    node (if available).
    The steps are the following:
    1. Create a dictionary with the nodes as keys and an empty list as value
    2. Create a list of counts of number of node seeing each peer
    3. Sort the peer list by count
    4. For each peer, get the list of nodes that see it, and select the best one
    following this rule: select the node with the lowest number of peers and, in
    case of a tie, select the one with the lowest latency.
    5. Return the dictionary of pairings
    """

    peer_list = {index: [] for index in range(input_array.shape[0])}

    # step 2
    count_list = []

    for col in range(input_array.shape[1]):
        count_list.append([col, np.count_nonzero(input_array[:, col])])

    # step 3
    sorted_peer_list = sorted(count_list, key=lambda x: x[1])
    sorted_peer_list = [item for item in sorted_peer_list if item[1] > 0]

    # step 4
    for peer_col, _ in sorted_peer_list:
        # get index of non-None values
        p_node_index = [
            [i, lat] for i, lat in enumerate(input_array[:, peer_col]) if lat
        ]
        length_list = [
            [index, len(peer_list[index]), lat] for index, lat in p_node_index
        ]

        # sort length_list by count and then by latency
        ordered_choice = sorted(length_list, key=lambda x: (x[1], x[2]))
        peer_list[ordered_choice[0][0]].append(peer_col)

    return_dict = dict()
    for key, value in peer_list.items():
        for item in value:
            return_dict[item] = key

    keys = list(return_dict.keys())
    keys.sort()

    return {i: return_dict[i] for i in keys}


def get_peer_list_from_dict(input_dict: dict) -> list:
    """
    This method returns the list of peers ids from the input dictionary.
    """
    peer_ids: list = []
    for peer_list in input_dict.values():
        for peer in peer_list:
            if peer in peer_ids:
                continue
            peer_ids.append(peer)

    return peer_ids


def get_node_list_from_dict(input_dict: dict) -> list:
    """
    This method returns the list of nodes ids from the input dictionary.
    """
    return list(input_dict.keys())


def dict_to_array(input_dict: dict, node_addresses: list, peer_ids: list):
    """
    This method converts the input dictionary to a numpy array based on nodes and
    peers ids orders.
    """

    outarray = np.zeros((len(node_addresses), len(peer_ids)))
    for node_idx, peer_list in enumerate(input_dict.values()):
        for peer, lat in peer_list.items():
            outarray[node_idx, peer_ids.index(peer)] = lat

    return outarray


def array_to_db_list(
    input_array: np.ndarray, matchs: dict, node_addresses: list, peer_ids: list
):
    """
    This method creates a list of tuples to be inserted in the database based on the
    input array and the matchs.
    """
    matchs_for_db = []
    for peer_idx, node_idxs in matchs.items():
        peer = peer_ids[peer_idx]
        nodes = [node_addresses[idx] for idx in node_idxs]
        latencies = [int(input_array[idx, peer_idx]) for idx in node_idxs]

        matchs_for_db.append((peer, nodes, latencies))

    return matchs_for_db


def remove_matchs(input_array: np.ndarray, matchs: dict) -> np.ndarray:
    """
    This method removes the matchs from the input array.
    """
    for key, value in matchs.items():
        input_array[value, key] = 0

    return input_array


def merge_matchs(matchs: list) -> dict:
    """
    This method merges the dictionaries in matchs so that each key has a list of values.
    """

    merged_matchs: dict[list] = dict()
    for match in matchs:
        for key, value in match.items():
            if key not in merged_matchs:
                merged_matchs[key] = []
            merged_matchs[key].append(value)

    return merged_matchs


def multiple_round_node_peer_match(
    input_array: np.ndarray, max_iter: int = None
) -> dict:
    """
    This method takes as input a matric of latencies between peers and nodes, and
    a maximum number of iterations, and returns a dictionary of pairings between peers
    and nodes.
    """
    matchs = []
    input = copy.deepcopy(input_array)

    iter = 0
    while np.sum(input) > 0:
        if max_iter and iter >= max_iter:
            break

        matchs.append(one_round_node_peer_match(input))
        input = remove_matchs(input, matchs[-1])
        iter += 1

    # merge the dictionaries in matchs so that each key has a list of values
    return merge_matchs(matchs)
