
# singleton metaclass
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
        self._list = []
        self._lock = threading.Lock() # thread-safe list
    
    def add(self, item):
        with self._lock:
            self._list.append(item)
    
    def get(self):
        with self._lock:
            return self._list
    
    def clear(self):
        with self._lock:
            self._list = []