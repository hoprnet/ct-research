import os
import time

from assets.parameters_schema import schema as schema_name
from celery import Celery
from tools import envvar, getlogger, read_json_on_gcp, write_csv_on_gcp

from .economic_model import EconomicModel
from .metric_table_entry import MetricTableEntry
from .peer import Peer
from .subgraph_entry import SubgraphEntry
from .topology_entry import TopologyEntry

log = getlogger()


def merge_topology_database_subgraph(
    topology_list: list[TopologyEntry],
    database_list: list[MetricTableEntry],
    subgraph_list: list[SubgraphEntry],
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
    for topology_entry in topology_list:
        peer = Peer(
            topology_entry.peer_id,
            topology_entry.node_address,
            topology_entry.channels_balance,
        )

        entries = [e for e in subgraph_list if e.hasAddress(peer.address)]
        if len(entries) > 1:
            subgraph_entry: SubgraphEntry = entries[0]
        else:
            subgraph_entry = SubgraphEntry(None, None, None)

        entries = [e for e in database_list if e.hasPeerId(peer.id)]
        if len(entries) > 1:
            database_entry: MetricTableEntry = entries[0]
        else:
            database_entry = MetricTableEntry(None, None, None, None)

        peer.node_ids = database_entry.node_ids
        peer.safe_address = subgraph_entry.safe_address
        peer.safe_balance = subgraph_entry.wxHoprBalance

        if peer.complete:
            merged_result.append(peer)

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

    model = EconomicModel.from_dictionary(contents)

    return model.budget.period / model.budget.distribution_frequency
