from asyncio import Queue

from prometheus_client import Gauge

from ..singleton import Singleton
from .message_format import MessageFormat

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer: Queue[MessageFormat] = Queue()

    async def get(self) -> MessageFormat:
        """Get message from queue and update gauge after operation completes."""
        item = await self._buffer.get()
        QUEUE_SIZE.set(self._buffer.qsize())
        return item

    async def put(self, item: MessageFormat):
        """Put message in queue and update gauge after operation completes."""
        await self._buffer.put(item)
        QUEUE_SIZE.set(self._buffer.qsize())

    @property
    def buffer(self) -> Queue[MessageFormat]:
        """Direct access to buffer (used for qsize checks in tests)."""
        return self._buffer
