import random

from janus import Queue
from prometheus_client import Gauge

from ..singleton import Singleton
from .message_format import MessageFormat

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue", ["index"])


class MessageQueue(metaclass=Singleton):
    def __init__(self, count: int = 5):
        self.count = count
        self.buffers = [Queue() for _ in range(self.count)]

    def sync_get(self, index: int) -> MessageFormat:
        index = index % self.count
        QUEUE_SIZE.labels(str(index)).set(self.size(index))
        return self.buffers[index].sync_q.get()

    def sync_put(self, item: MessageFormat, index: int = None):
        index = self._random_index() if index is None else (index % self.count)
        self.buffers[index].sync_q.put(item)

    async def async_get(self, index: int) -> MessageFormat:
        index = index % self.count
        QUEUE_SIZE.labels(str(index)).set(self.size(index))
        return await self.buffers[index].async_q.get()

    async def async_put(self, item: MessageFormat, index: int = None):
        index = self._random_index() if index is None else (index % self.count)
        await self.buffers[index].async_q.put(item)

    def size(self, index: int) -> int:
        return self.buffers[index].sync_q.qsize()

    def _random_index(self):
        return random.randint(0, self.count - 1)
