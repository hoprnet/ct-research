from asyncio import Queue

from prometheus_client import Gauge

from .singleton import Singleton
from .message_format import MessageFormat

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")
DEFAULT_QUEUE_MAXSIZE = 10_000


class MessageQueue(metaclass=Singleton):
    _configured_maxsize: int = DEFAULT_QUEUE_MAXSIZE

    def __init__(self):
        self._buffer: Queue[MessageFormat] = Queue(maxsize=self._configured_maxsize)

    @classmethod
    def configure_maxsize(cls, maxsize: int) -> None:
        cls._configured_maxsize = maxsize if maxsize > 0 else DEFAULT_QUEUE_MAXSIZE

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
