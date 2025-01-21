from asyncio import Queue

from prometheus_client import Gauge

from .singleton import Singleton

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")


class MessageFormat:
    def __init__(self, relayer: str, size: int):
        if size < 0:
            raise ValueError("Size must be a positive integer")
        self.relayer = relayer
        self.size = size

    @property
    def bytes(self):
        message_as_bytes = self.relayer.encode()
        if len(message_as_bytes) > self.size:
            raise ValueError("Encoded relayer length exceeds specified size")
        return message_as_bytes + b"\0" * (self.size - len(message_as_bytes))

class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer = Queue()

    async def get(self) -> MessageFormat:
        return await self.buffer.get()

    @property
    def buffer(self):
        QUEUE_SIZE.set(self._buffer.qsize())
        return self._buffer

    @classmethod
    def clear(cls):
        instance = cls()

        while not instance._buffer.empty():
            instance._buffer.get_nowait()
            instance._buffer.task_done()
            