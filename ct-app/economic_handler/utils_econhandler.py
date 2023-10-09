import os
import time

from celery import Celery
from sqlalchemy import func

from assets.parameters_schema import schema as schema_name
from tools import envvar, getlogger, write_csv_on_gcp, read_json_on_gcp
from tools.db_connection import DatabaseConnection, NodePeerConnection

from .peer import Peer
from .economic_model import EconomicModel

log = getlogger()


def merge_topology_database_subgraph(
    topology_dict: dict,
    database_dict: dict,
    subgraph_dict: dict,
):
    """
    Merge metrics and subgraph data with the unique peer IDs, addresses,
    balance links.
    :param: topology_dict: A dict mapping peer IDs to node addresses.
    :param: database_dict: A dict containing metrics with peer ID as the key.
    :param: subgraph_dict: A dict containing subgraph data with safe address as the key.
    :returns: A dict with peer ID as the key and the merged information.
    """
    merged_result: list[Peer] = []

    # Merge based on peer ID with the channel topology as the baseline
    for peer_id, data in topology_dict.items():
        peer = Peer(
            peer_id,
            data.get("source_node_address", None),
            data.get("channels_balance", None),
        )

        peer_in_subgraph: dict = subgraph_dict.get(peer.address, {})
        peer_in_database: dict = database_dict.get(peer.id, {})

        peer.node_ids = peer_in_database.get("node_peer_ids", None)
        peer.safe_address = peer_in_subgraph.get("safe_address", None)
        peer.safe_balance = peer_in_subgraph.get("wxHOPR_balance", None)

        if peer.complete:
            merged_result.append(peer)

    log.debug(f"Merged data sources: {merged_result}")
    log.info("Merged data successfully.")
    log.info("Total balance calculated successfully.")

    return merged_result


def exclude_elements(source_data: list[Peer], blacklist: list):
    """
    Removes elements from a dictionary based on a blacklist.
    :param: source_data (dict): The dictionary to be updated.
    :param: blacklist (list): A list containing the keys to be removed.
    :returns: nothing.
    """

    peer_ids = [peer.id for peer in source_data]
    indexes = [peer_ids.index(peer_id) for peer_id in blacklist if peer_id in peer_ids]

    # Remove elements from the list
    for index in sorted(indexes, reverse=True):
        peer: Peer = source_data.pop(index)
        log.info(f"Excluded {peer.id} from the dataset.")

    log.info(f"Excluded {len(indexes)} entries.")


def allow_many_node_per_safe(peers: list[Peer]):
    """
    Split the stake managed by a safe address equaly between the nodes
    that the safe manages.
    :param: peer: list of peers
    :returns: nothing.
    """
    safe_counts = {peer.safe_address: 0 for peer in peers}

    # Calculate the number of safe_addresses related to a node address
    for peer in peers:
        safe_counts[peer.safe_address] += 1

    # Update the input_dict with the calculated splitted_stake
    for peer in peers:
        peer.safe_address_count = safe_counts[peer.safe_address]

    log.info("Stake splitted successfully.")


def reward_probability(peers: list[Peer]):
    """
    Evaluate the function for each stake value in the eligible_peers dictionary.
    :param eligible_peers: A dict containing the data.
    :returns: nothing.
    """

    indexes_to_remove = [idx for idx, peer in enumerate(peers) if peer.has_low_stake]

    # remove entries from the list
    for index in sorted(indexes_to_remove, reverse=True):
        peers.pop(index=index)

    log.info(f"Excluded {len(indexes_to_remove)} peers from the dataset.")

    # compute ct probability
    total_tf_stake = sum(peer.transformed_stake for peer in peers)
    for peer in peers:
        peer.reward_probability = peer.transformed_stake / total_tf_stake

    log.info("Reward probabilty calculated successfully.")


# def compute_rewards(dataset: list[Peer]):
#     """
#     Computes the expected reward for each entry in the dataset, as well as the
#     number of job that must be executed per peer to satisfy the protocol reward.
#     :param: dataset: A dictionary containing the dataset entries.
#     """

#     budget = budget_param["budget"]["value"]
#     budget_split_ratio = budget_param["s"]["value"]
#     dist_freq = budget_param["dist_freq"]["value"]
#     budget_period_in_sec = budget_param["budget_period"]["value"]

#     for entry in dataset.values():
#         entry["budget"] = budget
#         entry["budget_split_ratio"] = budget_split_ratio
#         entry["distribution_frequency"] = dist_freq
#         entry["budget_period_in_sec"] = budget_period_in_sec

#         total_exp_reward = entry["prob"] * budget
#         apy_pct = (
#             (total_exp_reward * ((60 * 60 * 24 * 365) / budget_period_in_sec))
#             / entry["splitted_stake"]
#         ) * 100  # Splitted stake = total balance if 1 safe : 1 node
#         protocol_exp_reward = total_exp_reward * budget_split_ratio
#         entry["apy_pct"] = apy_pct

#         entry["total_expected_reward"] = total_exp_reward
#         entry["airdrop_expected_reward"] = total_exp_reward * (1 - budget_split_ratio)
#         entry["protocol_exp_reward"] = protocol_exp_reward

#         entry["protocol_exp_reward_per_dist"] = protocol_exp_reward / dist_freq

#         entry["ticket_price"] = budget_param["ticket_price"]["value"]
#         entry["winning_prob"] = budget_param["winning_prob"]["value"]

#         denominator = entry["ticket_price"] * entry["winning_prob"]
#         entry["jobs"] = round(entry["protocol_exp_reward_per_dist"] / denominator)

#     log.info("Expected rewards and jobs calculated successfully.")


def save_dict_to_csv(
    peers: list[Peer], filename_prefix: str = "file", foldername: str = "output"
) -> bool:
    """
    Saves a dictionary as a CSV file
    :param: peers:
    :param: filename_prefix (str): The prefix of the filename.
    :param: foldername (str): The name of the folder where the file will be saved.
    :returns: bool: No meaning except that it allows testing of the function.
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    file_path = os.path.join(foldername, filename)

    column_names = ["peer_id"] + list(peers[0].attribute_to_export().keys())

    lines = [column_names]

    for peer in peers:
        line = [peer.id] + list(peer.attribute_to_export().values())
        lines.append(line)

    write_csv_on_gcp("ct-platform-ct", file_path, lines)

    log.info("CSV file saved successfully")
    return True


def push_jobs_to_celery_queue(peers: list[Peer]):
    """
    Sends jobs to the celery queue including the number of jobs and an ordered
    list of postmans that execute the jobs.
    :param: peers:
    :returns: nothing.
    """
    app = Celery(
        name=envvar("PROJECT_NAME"),
        broker=envvar("CELERY_BROKER_URL"),
    )
    app.autodiscover_tasks(force=True)

    for peer in peers:
        node_list = peer.node_ids
        count = peer.message_count_for_reward
        node_index = 0

        app.send_task(
            envvar("TASK_NAME"),
            args=(peer.id, count, node_list, node_index),
            queue=node_list[node_index],
        )


async def get_database_metrics():
    """
    This function establishes a connection to the database using the provided
    connection details, retrieves the latest peer information from the database
    table, and returns the data as a dictionary.
    """
    with DatabaseConnection() as session:
        max_timestamp = session.query(func.max(NodePeerConnection.timestamp)).scalar()

        last_added_rows = (
            session.query(NodePeerConnection).filter_by(timestamp=max_timestamp).all()
        )

        metrics_dict = {}

        for row in last_added_rows:
            if row.peer_id not in metrics_dict:
                metrics_dict[row.peer_id] = {
                    "node_peer_ids": [],
                    "latency_metrics": [],
                    "timestamp": row.timestamp,
                    "temp_order": [],
                }
            metrics_dict[row.peer_id]["node_peer_ids"].append(row.node)
            metrics_dict[row.peer_id]["latency_metrics"].append(row.latency)
            metrics_dict[row.peer_id]["temp_order"].append(row.priority)

        # sort node_addresses and latency based on temp_order
        for peer_id in metrics_dict:
            order = metrics_dict[peer_id]["temp_order"]
            addresses = metrics_dict[peer_id]["node_peer_ids"]
            latency = metrics_dict[peer_id]["latency_metrics"]

            addresses = [x for _, x in sorted(zip(order, addresses))]
            latency = [x for _, x in sorted(zip(order, latency))]

            metrics_dict[peer_id]["node_peer_ids"] = addresses
            metrics_dict[peer_id]["latency_metrics"] = latency

        # remove the temp order key from the dictionaries
        for peer_id in metrics_dict:
            del metrics_dict[peer_id]["temp_order"]

        return "metricsDB", metrics_dict


def mock_data_metrics_db():
    """
    Generates a mock metrics dictionary that mimics the metrics database output.
    :returns: a dictionary containing mock metrics data with peer IDs and network
    watcher IDs odered by a statistical measure computed on latency
    """
    metrics_dict = {
        "peer_id_1": {
            "node_peer_ids": ["peerID_1", "peerID_2", "peerID_3"],
            "latency_metrics": [10, 15, 8],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_2": {
            "node_peer_ids": ["peerID_1", "peerID_3"],
            "latency_metrics": [5, 12, 7],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_3": {
            "node_peer_ids": ["peerID_1", "peerID_2", "peerID_3", "peerID_4"],
            "latency_metrics": [8, 18, 9],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_4": {
            "node_peer_ids": ["peerID_2", "peerID_3", "peerID_4"],
            "latency_metrics": [9, 14, 6],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_5": {
            "node_peer_ids": ["peerID_1", "peerID_3", "peerID_4"],
            "latency_metrics": [12, 20, 11],
            "timestamp": "2023-09-01 12:00:00",
        },
    }
    return metrics_dict


def mock_data_subgraph():
    """
    Generates a dictionary that mocks the metrics received form the subgraph.
    :returns: a dictionary containing the data with safe stake addresses as key
                and node_address as well as balance as the value.
    """
    subgraph_dict = {
        "address_1": {
            "safe_address": "safe_1",
            "wxHOPR_balance": int(20),
        },
        "address_2": {
            "safe_address": "safe_1",
            "wxHOPR_balance": int(30),
        },
        "address_3": {
            "safe_address": "safe_3",
            "wxHOPR_balance": int(40),
        },
        "address_4": {
            "safe_address": "safe_4",
            "wxHOPR_balance": int(50),
        },
        "address_5": {
            "safe_address": "safe_5",
            "wxHOPR_balance": int(80),
        },
    }
    return subgraph_dict


def replace_keys_in_mock_data(unique_nodeAddress_peerId_aggbalance_links: dict):
    """
    Just a helper function that allows me to replace my invented peerID's
    with the peerId's from Pluto.
    This function will be deleted when working with the real data.
    [NO NEED TO CHECK CODING STYLE NOR EFFICIENCY OF THE FUNCTION]
    """
    metrics_dict = mock_data_metrics_db()
    channel_topology_keys = list(unique_nodeAddress_peerId_aggbalance_links.keys())

    new_metrics_dict = {}
    for i, key in enumerate(metrics_dict.keys()):
        new_key = channel_topology_keys[i]
        new_metrics_dict[new_key] = metrics_dict[key]

    return new_metrics_dict


def economic_model_from_file(filename: str):
    """
    Reads parameters and equations from a JSON file and validates it using a schema.
    :param: filename (str): The name of the JSON file containing the parameters
    and equations. Defaults to "parameters.json".
    :returns: EconomicModel: Instance containing the model parameters,equations, budget
    parameters.
    """
    parameters_file_path = os.path.join("assets", filename)

    contents = read_json_on_gcp("ct-platform-ct", parameters_file_path, schema_name)

    model = EconomicModel.from_dictionary(contents)
    log.info("Fetched parameters and equations.")

    return model


def determine_delay_from_parameters(
    folder: str = "", filename: str = "parameters.json"
):
    """
    Determines the number of seconds from the JSON contents.
    :param folder: the folder where the parameters file is located
    :param filename: the name of the parameters file
    :returns: (int): The number of seconds to sleep
    """
    parameters_file_path = os.path.join(folder, filename)

    contents = read_json_on_gcp("ct-platform-ct", parameters_file_path, schema_name)

    period_in_seconds = contents["budget_param"]["budget_period"]["value"]
    distribution_count = contents["budget_param"]["dist_freq"]["value"]

    return period_in_seconds / distribution_count
