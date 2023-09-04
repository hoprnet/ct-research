import csv
import os
import time

from celery import Celery
from sqlalchemy import func

from assets.parameters_schema import schema as schema_name
from tools import envvar, getlogger, read_json_file
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
        source_node_address = data["source_node_address"]

        if peer_id in database_dict:
            metrics_data = database_dict[peer_id]
            data["node_peerIds"] = metrics_data["node_peerIds"]

        if source_node_address in subgraph_dict:
            subgraph_data = subgraph_dict[source_node_address]
            data["safe_address"] = subgraph_data["safe_address"]
            data["safe_balance"] = float(subgraph_data["wxHOPR_balance"])
            data["total_balance"] = data["channels_balance"] + data["safe_balance"]

        merged_result[peer_id] = data

    return merged_result


def block_ct_nodes(merged_metrics_dict: dict):
    """
    Exludes nodes from the ct distribution that are connected to
    Netwatcher/Postman modules.
    :param: merged_metrics_dict (dict): merged topology, subgraph, database data
    :returns: (dict): dictionary excluding ct-app instances
    """
    excluded_nodes = set()  # update a set to avoid duplicates

    # Collect all unique node_addresses from the input data
    for data in merged_metrics_dict.values():
        excluded_nodes.update(data["node_peerIds"])

    # New dictionary excluding entries with keys in the exclusion set
    metrics_dict_excluding_ct_nodes = {
        key: value
        for key, value in merged_metrics_dict.items()
        if key not in excluded_nodes
    }

    return metrics_dict_excluding_ct_nodes


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


def block_rpch_nodes(
    blacklist_rpch_nodes: list, merged_metrics_subgraph_topology: dict
):
    """
    Removes RPCh entry and exit nodes from the dictioanry that
    contains the merged results of database metrics, subgraph, and topology.
    :param: blacklist_rpch_nodes (list): Containing a list of RPCh nodes
    :param: merged_metrics_subgraph_topology (dict): merged data
    :returns: (dict): Updated merged_metrics_subgraph_topology dataset
    """
    merged_metrics_subgraph_topology = {
        k: v
        for k, v in merged_metrics_subgraph_topology.items()
        if k not in blacklist_rpch_nodes
    }
    return merged_metrics_subgraph_topology


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
        total_balance = value["total_balance"]
        value["safe_address_count"] = safe_address_counts[safe_address]

        value["splitted_stake"] = total_balance / value["safe_address_count"]


def compute_ct_prob(merged_result: dict, equations: dict, parameters: dict):
    """
    Evaluate the function for each stake value in the merged_result dictionary.
    :param: A dict containing the data.
    :param: equations: A dict containing the equations and conditions.
    :param: parameters: A dict containing the parameter values.
    :returns: A dict containing the probability distribution.
    """
    results = {}
    f_x_condition = equations["f_x"]["condition"]

    # compute transformed stake
    for key, value in merged_result.items():
        stake = value["splitted_stake"]
        params = {param: value["value"] for param, value in parameters.items()}
        params["x"] = stake

        try:
            function = "f_x" if eval(f_x_condition, params) else "g_x"
            formula = equations[function]["formula"]
            results[key] = {"trans_stake": eval(formula, params)}

        except Exception:
            log.exception(f"Error evaluating function for peer ID {key}")
            return

    # compute ct probability
    total_tf_stake = sum(result["trans_stake"] for result in results.values())

    for key in results:
        results[key]["prob"] = results[key]["trans_stake"] / total_tf_stake

    # update dictionary with model results
    for key in merged_result:
        if key in results:
            merged_result[key].update(results[key])


def compute_rewards(dataset: dict, budget_param: dict):
    """
    Computes the expected reward for each entry in the dataset, as well as the
    number of job that must be executed per peer to satisfy the protocol reward.
    :param: dataset (dict): A dictionary containing the dataset entries.
    :param: budget (dict): A dictionary containing the budget information.
    :returns: dict: The updated dataset with the 'expected_reward' value
    and reward splits for the automatic and airdrop mode.
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
        apy = (
            total_exp_reward * ((60 * 60 * 24 * 365) / budget_period_in_sec)
        ) / entry["total_balance"]
        protocol_exp_reward = total_exp_reward * budget_split_ratio
        entry["apy"] = apy

        entry["total_expected_reward"] = total_exp_reward
        entry["airdrop_expected_reward"] = total_exp_reward * (1 - budget_split_ratio)
        entry["protocol_exp_reward"] = protocol_exp_reward

        entry["protocol_exp_reward_per_dist"] = protocol_exp_reward / dist_freq

        entry["ticket_price"] = budget_param["ticket_price"]["value"]
        entry["winning_prob"] = budget_param["winning_prob"]["value"]

        denominator = entry["ticket_price"] * entry["winning_prob"]
        entry["jobs"] = round(entry["protocol_exp_reward_per_dist"] / denominator)

    return dataset


def save_expected_reward_csv(dataset: dict) -> bool:
    """
    Saves the expected rewards dictionary as a CSV file
    :param: dataset (dict): A dictionary containing the dataset entries.
    :returns: bool: No meaning except that it allows testing of the function.
    """
    timestamp = time.strftime("%Y%m%d%H%M%S")
    folder_name = "expected_rewards"
    folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_name)
    filename = f"expected_reward_{timestamp}.csv"
    file_path = os.path.join(folder_path, filename)

    try:
        os.makedirs(folder_path, exist_ok=True)
    except OSError:
        log.exception("Error occurred while creating the folder")
        return False

    try:
        with open(file_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            column_names = list(dataset.values())[0].keys()
            writer.writerow(["peer_id"] + list(column_names))
            for key, value in dataset.items():
                writer.writerow([key] + list(value.values()))
    except OSError:
        log.exception("Error occurred while writing to the CSV file")
        return False

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
        name="client",
        broker=envvar("CELERY_BROKER_URL"),
        backend=envvar("CELERY_RESULT_BACKEND"),
        include=["celery_tasks"],
    )
    app.autodiscover_tasks(force=True)

    for peer_id, value in dataset.items():
        node_list = value["node_addresses"]
        count = value["jobs"]
        node_index = 0

        app.send_task(
            f"{envvar('TASK_NAME')}.{node_list[node_index]}",
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
                    "node_peerIds": [],
                    "latency_metrics": [],
                    "timestamp": row.timestamp,
                    "temp_order": [],
                }
            metrics_dict[row.peer_id]["node_peerIds"].append(row.node)
            metrics_dict[row.peer_id]["latency_metrics"].append(row.latency)
            metrics_dict[row.peer_id]["temp_order"].append(row.priority)

        # sort node_addresses and latency based on temp_order
        for peer_id in metrics_dict:
            order = metrics_dict[peer_id]["temp_order"]
            addresses = metrics_dict[peer_id]["node_peerIds"]
            latency = metrics_dict[peer_id]["latency_metrics"]

            addresses = [x for _, x in sorted(zip(order, addresses))]
            latency = [x for _, x in sorted(zip(order, latency))]

            metrics_dict[peer_id]["node_peerIds"] = addresses
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
            "node_peerIds": ["peerID_1", "peerID_2", "peerID_3"],
            "latency_metrics": [10, 15, 8],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_2": {
            "node_peerIds": ["peerID_1", "peerID_3"],
            "latency_metrics": [5, 12, 7],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_3": {
            "node_peerIds": ["peerID_1", "peerID_2", "peerID_3", "peerID_4"],
            "latency_metrics": [8, 18, 9],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_4": {
            "node_peerIds": ["peerID_2", "peerID_3", "peerID_4"],
            "latency_metrics": [9, 14, 6],
            "timestamp": "2023-09-01 12:00:00",
        },
        "peer_id_5": {
            "node_peerIds": ["peerID_1", "peerID_3", "peerID_4"],
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


def economic_model_from_file(filename: str = "parameters.json"):
    """
    Reads parameters and equations from a JSON file and validates it using a schema.
    :param: filename (str): The name of the JSON file containing the parameters
    and equations. Defaults to "parameters.json".
    :returns: dicts: The first dictionary contains the model parameters, the second
    dictionary contains the equations, and the third dictionary
    contains the budget parameters.
    """
    script_directory = os.path.dirname(os.path.abspath(__file__))
    assets_directory = os.path.join(script_directory, "../assets")
    parameters_file_path = os.path.join(assets_directory, filename)

    contents = read_json_file(parameters_file_path, schema_name)

    return contents["equations"], contents["parameters"], contents["budget_param"]
