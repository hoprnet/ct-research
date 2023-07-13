import threading
import datetime

from tools.db_connection import DatabaseConnection

from .utils import (
    array_to_db_list,
    dict_to_array,
    get_nw_list_from_dict,
    get_peer_list_from_dict,
    multiple_round_nw_peer_match,
)


class Singleton(type):
    """
    Singleton metaclass.
    A class that uses this metaclass can only be instantiated once. All subsequent
    calls to the constructor will return the same instance.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        # if instance exists, return it
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        # otherwise, create it and return it
        return cls._instances[cls]


class Aggregator(metaclass=Singleton):
    """
    Aggregator class.
    This class is used to store the latency data received from the pods.
    It is implemented as a singleton, so that it can be accessed from different
    threads and parts of the code.

    It is implemented using threading locks to ensure concurrency safety.
    """

    def __init__(
        self,
        db: str = None,
        dbhost: str = None,
        dbuser: str = None,
        dbpassword: str = None,
        dbport: str = None,
    ):
        self._nw_peer_latency: dict = {}
        self._nw_peer_latency_lock = threading.Lock()  # thread-safe nw_peer_latency

        self._nw_last_update: dict = {}
        self._nw_last_update_lock = threading.Lock()  # thread-safe last_update

        self._nw_balances: dict = {}
        self._nw_balances_lock = threading.Lock()  # thread-safe balances

        self.db = DatabaseConnection(
            database=db, host=dbhost, user=dbuser, password=dbpassword, port=dbport
        )

    def add_nw_peer_latencies(self, pod_id: str, items: list):
        """
        Add latency data to the aggregator for a specific pod (nw).
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to add the latency data for
        :param items: the latency data to add
        :return: Nothing
        """

        with self._nw_peer_latency_lock:
            if pod_id not in self._nw_peer_latency:
                self._nw_peer_latency[pod_id] = {}

            for peer, lat in items.items():
                self._nw_peer_latency[pod_id][peer] = lat

    def get_nw_peer_latencies(self) -> dict:
        """
        Get the latency data stored.
        Concurrent access is managed using a lock.
        :return: the latency data stored
        """
        with self._nw_peer_latency_lock:
            return self._nw_peer_latency

    def clear_nw_peer_latencies(self):
        """
        Clear the latency data stored.
        Concurrent access is managed using a lock.
        :return: Nothing
        """
        with self._nw_peer_latency_lock:
            self._nw_peer_latency = {}

    def set_nw_update(self, pod_id: str, timestamp: datetime.datetime):
        """
        Set the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to set the last update timestamp for
        :param timestamp: the last update timestamp for the specified pod
        :return: Nothing
        """
        with self._nw_last_update_lock:
            self._nw_last_update[pod_id] = timestamp

    def get_nw_update(self, pod_id: str) -> datetime.datetime:
        """
        Get the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to get the last update timestamp for
        :return: the last update timestamp for the specified pod
        """
        with self._nw_last_update_lock:
            if pod_id not in self._nw_last_update:
                return None
            return self._nw_last_update[pod_id]

    def clear_nw_update(self):
        """
        Clear the last update timestamp stored.
        Concurrent access is managed using a lock.
        :return: Nothing
        """
        with self._nw_last_update_lock:
            self._nw_last_update = {}

    def add_nw_balance(self, pod_id: str, token: str, balance: float):
        """
        Add a balance for a specific pod.
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to add the balance for
        :param token: the token for which the balance is added
        :param balance: the balance to add
        :return: Nothing
        """
        with self._nw_balances_lock:
            if pod_id not in self._nw_balances:
                self._nw_balances[pod_id] = {}

            self._nw_balances[pod_id][token] = balance

    def get_nw_balances(self) -> dict:
        """
        Get the balances stored.
        Concurrent access is managed using a lock.
        :return: the balances stored
        """
        with self._nw_balances_lock:
            return self._nw_balances

    def clear_nw_balances(self):
        """
        Clear the balances stored.
        Concurrent access is managed using a lock.
        :return: Nothing
        """
        with self._nw_balances_lock:
            self._nw_balances = {}

    def convert_to_db_data(self):
        """
        Convert the data stored in self._dict to a list of tuples, describing for each
        peer the list of best nw to connect to and the corresponding latencies.
        """
        with self._nw_peer_latency_lock:
            # gather all nw ids in a single list
            nw_ids = get_nw_list_from_dict(self._nw_peer_latency)
            peer_ids = get_peer_list_from_dict(self._nw_peer_latency)

            # create an array with latencies stored at the right indexes, corresponding
            # to nw and peer indexes in the lists above
            lat_as_array = dict_to_array(self._nw_peer_latency, nw_ids, peer_ids)

            # create a dict with the best 'peer: [nw]' matchs
            matchs = multiple_round_nw_peer_match(lat_as_array, max_iter=3)

            # convert back each ids in matchs to the original ids
            matchs_for_db = array_to_db_list(lat_as_array, matchs, nw_ids, peer_ids)

        return matchs_for_db

    def get_metrics(self):
        metrics = {"peers": {}, "netwatchers": {}, "aggregator": {}}

        with self._nw_balances_lock:
            for nw_id, balances in self.get_nw_balances().items():
                if nw_id not in metrics["netwatchers"]:
                    metrics["netwatchers"][nw_id] = {}
                metrics["netwatchers"][nw_id]["balances"] = balances

        with self._nw_peer_latencies_lock:
            for _, latencies in self.get_nw_peer_latencies().items():
                for peer_id, latency in latencies.items():
                    if peer_id not in metrics["peers"]:
                        metrics["peers"][peer_id] = {}

                    metrics["peers"][peer_id] = latency

        return metrics
