import threading
import datetime
from .utils import (array_to_db_list, dict_to_array, 
                   get_nw_list_from_dict, get_peer_list_from_dict, 
                   multiple_round_nw_peer_match)

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
        self._dict: dict = {}
        self._update_dict: dict = {}
        self._dict_lock = threading.Lock()  # thread-safe list
        self._update_lock = threading.Lock()  # thread-safe lastupdate

        # db connection information
        self.db = db
        self.dbhost = dbhost
        self.dbuser = dbuser
        self.dbpassword = dbpassword
        self.dbport = dbport

    def add(self, pod_id: str, items: list):
        """
        Add latency data to the aggregator for a specific pod (nw).
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to add the latency data for
        :param items: the latency data to add
        :return: Nothing
        """

        with self._dict_lock:
            if pod_id not in self._dict:
                self._dict[pod_id] = {}

            for peer, lat in items.items():
                self._dict[pod_id][peer] = lat

    def get(self) -> dict:
        """
        Get the latency data stored.
        Concurrent access is managed using a lock.
        :return: the latency data stored
        """
        with self._dict_lock:
            return self._dict

    def clear(self):
        """
        Clear the latency data stored.
        Concurrent access is managed using a lock.
        :return: Nothing
        """
        with self._dict_lock:
            self._dict = {}

    def set_update(self, pod_id: str, timestamp: datetime.datetime):
        """
        Set the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to set the last update timestamp for
        :param timestamp: the last update timestamp for the specified pod
        :return: Nothing
        """
        with self._update_lock:
            self._update_dict[pod_id] = timestamp

    def get_update(self, pod_id: str) -> datetime.datetime:
        """
        Get the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        :param pod_id: the pod id (nw id) to get the last update timestamp for
        :return: the last update timestamp for the specified pod
        """
        with self._update_lock:
            if pod_id not in self._update_dict:
                return None
            return self._update_dict[pod_id]

    def convert_to_db_data(self):
        """
        Convert the data stored in self._dict to a list of tuples, describing for each
        peer the list of best nw to connect to and the corresponding latencies.
        """
        with self._dict_lock:
            # gather all nw ids in a single list
            nw_ids = get_nw_list_from_dict(self._dict)
            peer_ids = get_peer_list_from_dict(self._dict)

            # create an array with latencies stored at the right indexes, corresponding
            # to nw and peer indexes in the lists above
            lat_as_array = dict_to_array(self._dict, nw_ids, peer_ids)

            # create a dict with the best 'peer: [nw]' matchs
            matchs = multiple_round_nw_peer_match(lat_as_array, max_iter=3)

            # convert back each ids in matchs to the original ids
            matchs_for_db = array_to_db_list(lat_as_array, matchs, nw_ids, peer_ids)

        return matchs_for_db

    def get_metrics(self):
        with self._dict_lock:
            metrics = {}

        return metrics
