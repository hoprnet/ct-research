# enum class with auto numbering
import numpy as np
import copy

def template(input_array: np.ndarray) -> dict:
    peer_list = {index: [] for index in range(input_array.shape[0])}

    # step 2
    count_list = []

    for col in range(input_array.shape[1]):        
        count_list.append([col, np.count_nonzero(input_array[:,col])])
    
    # step 3
    sorted_peer_list = sorted(count_list, key=lambda x: x[1])
    sorted_peer_list = [item for item in sorted_peer_list if item[1] > 0]

    # step 4
    for peer_col, _ in sorted_peer_list:
        # get index of non-None values
        p_nw_index = [[i, lat] for i, lat in enumerate(input_array[:,peer_col]) if lat]
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

def remove_matchs(input_array: np.ndarray, matchs: dict) -> np.ndarray:
    for key, value in matchs.items():
        input_array[value, key] = 0
        
    return input_array

def merge_matchs(matchs: list) -> dict:
    merged_matchs: dict[list] = dict()
    for match in matchs:
        for key, value in match.items():
            if key not in merged_matchs:
                merged_matchs[key] = []
            merged_matchs[key].append(value)

    return merged_matchs

def get_best_matchs(input_array: np.ndarray, max_iter:int = None) -> dict:
    matchs = []
    input = copy.deepcopy(input_array)

    iter = 0
    while np.sum(input) > 0:
        if max_iter and iter >= max_iter:
            break

        matchs.append(template(input))
        input = remove_matchs(input, matchs[-1])
        iter += 1

    # merge the dictionaries in matchs so that each key has a list of values
    return merge_matchs(matchs)