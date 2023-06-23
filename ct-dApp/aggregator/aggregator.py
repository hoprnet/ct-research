from datetime import datetime
import threading

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
    def __init__(self):
        self._dict: dict = {}
        self._update_dict: dict = {}
        self._dict_lock = threading.Lock() # thread-safe list
        self._update_lock = threading.Lock() # thread-safe lastupdate
    
    def add(self, pod_id : str, items: list):
        """
        Add latency data to the aggregator for a specific pod (nw).
        Concurrent access is managed using a lock.
        """

        with self._dict_lock:
            if pod_id not in self._dict:
                self._dict[pod_id] = {}

            for peer, lat in items.items():
                self._dict[pod_id][peer] = lat

    def get(self):
        """
        Get the latency data stored.
        Concurrent access is managed using a lock.
        """
        with self._dict_lock:
            return self._dict
    
    def clear(self):
        """
        Clear the latency data stored.
        Concurrent access is managed using a lock.
        """
        with self._dict_lock:
            self._dict = {}

    def set_update(self, pod_id: str, timestamp: datetime):
        """
        Set the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        """
        with self._update_lock:
            self._update_dict[pod_id] = timestamp

    def get_update(self, pod_id: str):
        """
        Get the last update timestamp for a specific pod.
        Concurrent access is managed using a lock.
        """
        with self._update_lock:
            if pod_id not in self._update_dict:
                return None
            return self._update_dict[pod_id]