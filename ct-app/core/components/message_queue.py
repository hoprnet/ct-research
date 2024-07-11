from asyncio import Queue

from prometheus_client import Gauge

from .singleton import Singleton

queue_size = Gauge("ct_queue_size", "Size of the message queue")


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer = Queue()

    @property
    def buffer(self):
        queue_size.set(self._buffer.qsize())
        return self._buffer
