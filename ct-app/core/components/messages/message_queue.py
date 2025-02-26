from janus import Queue
from prometheus_client import Gauge

from ..singleton import Singleton
from .message_format import MessageFormat

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer = Queue()

    def get_sync(self) -> MessageFormat:
        return self.buffer.sync_q.get()

    def put_sync(self, item: MessageFormat):
        self.buffer.sync_q.put(item)

    async def get_async(self) -> MessageFormat:
        return await self.buffer.async_q.get()

    async def put_async(self, item: MessageFormat):
        self.buffer.async_q.put(item)

    @property
    def size(self):
        return self._buffer.sync_q.qsize()

    @property
    def buffer(self):
        QUEUE_SIZE.set(self.size)
        return self._buffer

    @classmethod
    def clear(cls):
        while not cls().size:
            cls().get_sync()