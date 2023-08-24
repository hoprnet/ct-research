import datetime
import threading

from prometheus_client.metrics import Gauge

from tools import getlogger
from tools.db_connection import NodePeerConnection

from .utils import (
    array_to_db_list,
    dict_to_array,
    get_node_list_from_dict,
    get_peer_list_from_dict,
    multiple_round_node_peer_match,
)

log = getlogger()


class Singleton(type):
    """
    Singleton metaclass.
    A class that uses this metaclass can only be instantiated once. All subsequent
    calls to the constructor will return the same instance.
    """

    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        # if instance exists, return it
        # otherwise, create it and return it
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]


class Aggregator(metaclass=Singleton):
    """
    Aggregator class.
    This class is used to store the latency data received from the pods.
    It is implemented as a singleton, so that it can be accessed from different
    threads and parts of the code.

    It is implemented using threading locks to ensure concurrency safety.
    """

    def __init__(self):
        self._node_peer_latency: dict = {}
        self._node_peer_latency_lock = threading.Lock()  # thread-safe node_peer_latency

        self._node_last_update: dict = {}
        self._node_last_update_lock = threading.Lock()  # thread-safe last_update

        self._node_balances: dict = {}
        self._node_balances_lock = threading.Lock()  # thread-safe balances

        self.prometheus_balance = Gauge(
            "node_balance", "Node balance", ["node_address", "token"]
        )
        self.prometheus_latency = Gauge(
            "peer_latency", "Last peer latency measured", ["node_address", "peer_id"]
        )
        self.prometheus_node_update = Gauge(
            "node_update", "Last node update received", ["node_address"]
        )

    def add_node_peer_latencies(self, node_id: str, items: dict):
        """
        Add latency data to the aggregator for a specific node.
        Concurrent access is managed using a lock.
        :param node_id: the node id to add the latency data for
        :param items: the latency data to add
        :return: Nothing
        """

        with self._node_peer_latency_lock:
            if node_id not in self._node_peer_latency:
                self._node_peer_latency[node_id] = {}

            for peer, lat in items.items():
                self._node_peer_latency[node_id][peer] = lat

            log.info(f"Added latency data for node {node_id}")

        for peer, lat in items.items():
            self.prometheus_latency.labels(node_id, peer).set(lat)

    def get_node_peer_latencies(self) -> dict:
        """
        Get the latency data stored.
        Concurrent access is managed using a lock.
        :return: the latency data stored
        """
        with self._node_peer_latency_lock:
            log.info("Accessed latency data")

            return self._node_peer_latency

    def set_node_update(self, node_id: str, timestamp: datetime.datetime):
        """
        Set the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param node_id: the node id to set the last update timestamp for
        :param timestamp: the last update timestamp for the specified pod
        :return: Nothing
        """
        with self._node_last_update_lock:
            self._node_last_update[node_id] = timestamp

            log.info(f"Set last update timestamp for node {node_id} to {timestamp}")

        self.prometheus_node_update.labels(node_id).set(timestamp.timestamp())

    def get_node_update(self, node_id: str) -> datetime.datetime:
        """
        Get the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param node_id: the node id to get the last update timestamp for
        :return: the last update timestamp for the specified pod
        """
        with self._node_last_update_lock:
            if node_id not in self._node_last_update:
                log.error(f"Requested last update timestamp for unknown node {node_id}")
                return None

            log.info(f"Accessed last update timestamp for node {node_id}")
            return self._node_last_update[node_id]

    def clear_node_update(self):
        """
        Clear the last update timestamp stored.
        Concurrent access is managed using a lock.
        :return: Nothing
        """
        with self._node_last_update_lock:
            self._node_last_update = {}
            log.info("Cleared last update timestamps")

    def add_node_balance(self, node_id: str, token: str, balance: float):
        """
        Add a balance for a specific pod.
        Concurrent access is managed using a lock.
        :param node_id: the node id to add the balance for
        :param token: the token for which the balance is added
        :param balance: the balance to add
        :return: Nothing
        """
        self.prometheus_balance.labels(node_id, token).set(balance)

    def convert_to_db_data(self):
        """
        Convert the data stored in self._dict to a list of tuples, describing for each
        peer the list of best node to connect to and the corresponding latencies.
        """
        with self._node_peer_latency_lock:
            # gather all node ids in a single list
            node_addresses = get_node_list_from_dict(self._node_peer_latency)
            log.info(f"Nodes going to be matched: {node_addresses}")

            peer_ids = get_peer_list_from_dict(self._node_peer_latency)
            log.info(f"Peers going to be matched: {peer_ids}")

            # create an array with latencies stored at the right indexes, corresponding
            # to node and peer indexes in the lists above
            lat_as_array = dict_to_array(
                self._node_peer_latency, node_addresses, peer_ids
            )
            log.debug(f"Latency data converted into an array:\n{lat_as_array}")

            # create a dict with the best 'peer: [node]' matchs
            matchs = multiple_round_node_peer_match(lat_as_array, max_iter=3)
            log.info(f"Matchs with 3 iterations:\n{matchs}")

            # convert back each ids in matchs to the original ids
            matchs_for_db = array_to_db_list(
                lat_as_array, matchs, node_addresses, peer_ids
            )
            log.info(f"Matchs for db:\n{matchs_for_db}")

        timestamp = datetime.datetime.now()

        return [
            NodePeerConnection(
                peer_id=item[0],
                node=item[1],
                latency=item[2],
                priority=item[3],
                timestamp=timestamp,
            )
            for item in matchs_for_db
        ]
