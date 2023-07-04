# enum class with auto numbering
import copy

import numpy as np

def one_round_nw_peer_match(input_array: np.ndarray) -> dict:
    """
    This method implements the pairing between netwatchers and peers for one round.
    At the end of the execution of this method, each peer will be paired with one
    netwatcher (if available).
    The steps are the following:
    1. Create a dictionary with the netwatchers as keys and an empty list as value
    2. Create a list of counts of number of netwatcher seeing each peer
    3. Sort the peer list by count
    4. For each peer, get the list of netwatchers that see it, and select the best one
    following this rule: select the netwatcher with the lowest number of peers and, in
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
        p_nw_index = [[i, lat] for i, lat in enumerate(input_array[:, peer_col]) if lat]
        length_list = [[index, len(peer_list[index]), lat] for index, lat in p_nw_index]

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
    
def get_nw_list_from_dict(input_dict: dict) -> list:
    """
    This method returns the list of netwatchers ids from the input dictionary.
    """
    return list(input_dict.keys())

def dict_to_array(input_dict: dict, nw_ids: list, peer_ids: list):
    """
    This method converts the input dictionary to a numpy array based on netwatchers and
    peers ids orders.
    """

    outarray = np.zeros((len(nw_ids), len(peer_ids)))
    for nw_idx, peer_list in enumerate(input_dict.values()):
        for peer, lat in peer_list.items():
            outarray[nw_idx, peer_ids.index(peer)] = lat

    return outarray

def array_to_db_list(input_array: np.ndarray, matchs: dict, nw_ids: list, peer_ids: list):
    """
    This method create a list of tuples to be inserted in the database based on the 
    input array and the matchs.
    """
    matchs_for_db = []
    for peer_idx, nw_idxs in matchs.items():
        peer = peer_ids[peer_idx]
        nws = [nw_ids[idx] for idx in nw_idxs]
        latencies = [int(input_array[idx, peer_idx]) for idx in nw_idxs]

        matchs_for_db.append((peer, nws, latencies))
        
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

def multiple_round_nw_peer_match(input_array: np.ndarray, max_iter: int = None) -> dict:
    """
    This method takes as input a matric of latencies between peers and netwatchers, and
    a maximum number of iterations, and returns a dictionary of pairings between peers
    and netwatchers.
    """
    matchs = []
    input = copy.deepcopy(input_array)

    iter = 0
    while np.sum(input) > 0:
        if max_iter and iter >= max_iter:
            break

        matchs.append(one_round_nw_peer_match(input))
        input = remove_matchs(input, matchs[-1])
        iter += 1

    # merge the dictionaries in matchs so that each key has a list of values
    return merge_matchs(matchs)
