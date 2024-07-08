from asyncio import Queue
from typing import Any

from .singleton import Singleton


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self.buffer = Queue()

    async def publish(self, message: Any):
        await self.buffer.put(message)
