from datetime import datetime
import threading

class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        # if instance exists, return it
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        # otherwise, create it and return it
        return cls._instances[cls]
    
# aggregator class
class Aggregator(metaclass=Singleton):
    def __init__(self):
        self._dict: dict = {}
        self._update: datetime = None
        self._dict_lock = threading.Lock() # thread-safe list
        self._update_lock = threading.Lock() # thread-safe lastupdate
    
    def add(self, pod_id:str, items: list):
        with self._dict_lock:
            if pod_id not in self._dict:
                self._dict[pod_id] = set()
            self._dict[pod_id].update(items)

    def get(self):
        with self._dict_lock:
            return self._dict
    
    def clear(self):
        with self._dict_lock:
            self._dict = {}

    def set_update(self, timestamp:datetime):
        with self._update_lock:
            self._update = timestamp

    def get_update(self):
        with self._update_lock:
            return self._update