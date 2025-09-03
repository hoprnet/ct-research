from asyncio import Queue

from prometheus_client import Gauge

from ..singleton import Singleton
from .message_format import MessageFormat

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer = Queue()

    async def get(self) -> MessageFormat:
        return await self.buffer.get()

    async def put(self, item: MessageFormat):
        await self.buffer.put(item)

    @property
    def buffer(self):
        QUEUE_SIZE.set(self._buffer.qsize())
        return self._buffer
