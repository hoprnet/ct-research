from asyncio import Queue

from .singleton import Singleton


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self.buffer = Queue()

    async def publish(self, message):
        await self.buffer.put(message)
