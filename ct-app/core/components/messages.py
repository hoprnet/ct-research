import os
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

    @classmethod
    def clear(cls):
        instance = cls()

        while not instance._buffer.empty():
            instance._buffer.get_nowait()
            instance._buffer.task_done()


class MessageFormat:
    def __init__(self, relayer: str, size: int):
        self.relayer = relayer
        self.size = size

    @property
    def bytes(self):
        message_as_bytes = self.relayer.encode()
        return message_as_bytes + b"\0" * (self.size - len(message_as_bytes))
