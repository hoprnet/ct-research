import os
import time

from celery import Celery
from sqlalchemy import func

from assets.parameters_schema import schema as schema_name
from tools import envvar, getlogger, write_csv_on_gcp, read_json_on_gcp
from tools.db_connection import DatabaseConnection, NodePeerConnection

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
    merged_result = {}

    # Merge based on peer ID with the channel topology as the baseline
    for peer_id, data in topology_dict.items():
        log.debug(f"Peer {peer_id} seen in topology")
        seen_in_database = False
        seen_in_subgraph = False

        if peer_id in database_dict:
            metrics_data = database_dict[peer_id]
            data["node_peer_ids"] = metrics_data["node_peer_ids"]
            seen_in_database = True
            log.debug(f"Peer {peer_id} found in database")

        source_node_address = data["source_node_address"]
        if source_node_address in subgraph_dict:
            subgraph_data = subgraph_dict[source_node_address]
            data["safe_address"] = subgraph_data["safe_address"]
            data["safe_balance"] = float(subgraph_data["wxHOPR_balance"])
            data["total_balance"] = data["channels_balance"] + data["safe_balance"]

            seen_in_subgraph = True
            log.debug(f"Source node address for {peer_id} found in subgraph")

        log.debug(f"{peer_id}:{seen_in_database}, {seen_in_subgraph}")

        if seen_in_database and seen_in_subgraph:
            merged_result[peer_id] = data

    log.debug(f"Merged data sources: {merged_result}")
    log.info("Merged data successfully.")
    log.info("Total balance calculated successfully.")

    return merged_result


def exclude_elements(source_data: dict, blacklist: list):
    """
    Removes elements from a dictionary based on a blacklist.
    :param: source_data (dict): The dictionary to be updated.
    :param: blacklist (list): A list containing the keys to be removed.
    :returns: nothing.
    """

    for key in blacklist:
        if key not in source_data:
            continue
        del source_data[key]

    log.info(f"Excluded up to {len(blacklist)} entries.")


def allow_many_node_per_safe(input_dict: dict):
    """
    Split the stake managed by a safe address equaly between the nodes
    that the safe manages.
    :param: input_dict: dictionary containing peerID, nodeAddress, safeAdress
        and total balance.
    :returns: nothing.
    """
    safe_address_counts = {}

    # Calculate the number of safe_addresses related to a node address
    for value in input_dict.values():
        safe_address = value["safe_address"]

        if safe_address not in safe_address_counts:
            safe_address_counts[safe_address] = 0

        safe_address_counts[safe_address] += 1

    # Update the input_dict with the calculated splitted_stake
    for value in input_dict.values():
        safe_address = value["safe_address"]
        channels_balance = value["channels_balance"]
        safe_balance = value["safe_balance"]
        value["safe_address_count"] = safe_address_counts[safe_address]

        value["splitted_stake"] = (
            safe_balance / value["safe_address_count"]
        ) + channels_balance

    log.info("Stake splitted successfully.")


def reward_probability(eligible_peers: dict, equations: dict, parameters: dict):
    """
    Evaluate the function for each stake value in the eligible_peers dictionary.
    :param eligible_peers: A dict containing the data.
    :param: equations: A dict containing the equations and conditions.
    :param: parameters: A dict containing the parameter values.
    :returns: nothing.
    """
    results = {}
    f_x_condition = equations["f_x"]["condition"]

    # compute transformed stake
    params = {param: value["value"] for param, value in parameters.items()}

    for peer in eligible_peers:
        params["x"] = eligible_peers[peer]["splitted_stake"]

        try:
            function = "f_x" if eval(f_x_condition, params) else "g_x"
            formula = equations[function]["formula"]
            results[peer] = {"trans_stake": eval(formula, params)}

        except Exception:
            log.exception(f"Error evaluating function for peer ID {peer}")
            return

    # compute ct probability
    total_tf_stake = sum(result["trans_stake"] for result in results.values())

    for key in results:
        results[key]["prob"] = results[key]["trans_stake"] / total_tf_stake

    # update dictionary with model results
    for key in eligible_peers:
        if key in results:
            eligible_peers[key].update(results[key])

    log.info("Reward probabilty calculated successfully.")


def compute_rewards(dataset: dict, budget_param: dict):
    """
    Computes the expected reward for each entry in the dataset, as well as the
    number of job that must be executed per peer to satisfy the protocol reward.
    :param: dataset (dict): A dictionary containing the dataset entries.
    :param: budget (dict): A dictionary containing the budget information.
    """
    budget = budget_param["budget"]["value"]
    budget_split_ratio = budget_param["s"]["value"]
    dist_freq = budget_param["dist_freq"]["value"]
    budget_period_in_sec = budget_param["budget_period"]["value"]

    for entry in dataset.values():
        entry["budget"] = budget
        entry["budget_split_ratio"] = budget_split_ratio
        entry["distribution_frequency"] = dist_freq
        entry["budget_period_in_sec"] = budget_period_in_sec

        total_exp_reward = entry["prob"] * budget
        apy_pct = (
            (total_exp_reward * ((60 * 60 * 24 * 365) / budget_period_in_sec))
            / entry["splitted_stake"]
        ) * 100  # Splitted stake = total balance if 1 safe : 1 node
        protocol_exp_reward = total_exp_reward * budget_split_ratio
        entry["apy_pct"] = apy_pct

        entry["total_expected_reward"] = total_exp_reward
        entry["airdrop_expected_reward"] = total_exp_reward * (1 - budget_split_ratio)
        entry["protocol_exp_reward"] = protocol_exp_reward

        entry["protocol_exp_reward_per_dist"] = protocol_exp_reward / dist_freq

        entry["ticket_price"] = budget_param["ticket_price"]["value"]
        entry["winning_prob"] = budget_param["winning_prob"]["value"]

        denominator = entry["ticket_price"] * entry["winning_prob"]
        entry["jobs"] = round(entry["protocol_exp_reward_per_dist"] / denominator)

        print(f"{entry}")

    log.info("Expected rewards and jobs calculated successfully.")


def save_dict_to_csv(
    data: dict, filename_prefix: str = "file", foldername: str = "output"
) -> bool:
    """
    Saves a dictionary as a CSV file
    :param: data (dict): A dictionary to be saved.
    :param: filename_prefix (str): The prefix of the filename.
    :param: foldername (str): The name of the folder where the file will be saved.
    :returns: bool: No meaning except that it allows testing of the function.
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.csv"
    file_path = os.path.join(foldername, filename)

    column_names = ["peer_id"] + list(list(data.values())[0].keys())

    lines = [column_names]

    print(f"{column_names=}")
    print(f"{lines=}")
    print(f"{data=}")
    for key, value in data.items():
        lines.append([key] + list(value.values()))

    write_csv_on_gcp("ct-platform-ct", file_path, lines)

    log.info("CSV file saved successfully")
    return True


def push_jobs_to_celery_queue(dataset: dict):
    """
    Sends jobs to the celery queue including the number of jobs and an ordered
    list of postmans that execute the jobs.
    :param: dataset (dict): Contains the job number and postman list by peer id.
    :returns: nothing.
    """
    app = Celery(
        name=envvar("PROJECT_NAME"),
        broker=envvar("CELERY_BROKER_URL"),
    )
    app.autodiscover_tasks(force=True)

    for peer_id, value in dataset.items():
        node_list = value["node_peer_ids"]
        count = value["jobs"]
        node_index = 0

        app.send_task(
            envvar("TASK_NAME"),
            args=(peer_id, count, node_list, node_index),
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
    :returns: dicts: The first dictionary contains the model parameters, the second
    dictionary contains the equations, and the third dictionary
    contains the budget parameters.
    """
    parameters_file_path = os.path.join("assets", filename)

    contents = read_json_on_gcp("ct-platform-ct", parameters_file_path, schema_name)

    log.info("Fetched parameters and equations.")
    return contents["equations"], contents["parameters"], contents["budget_param"]
