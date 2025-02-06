import re
import uuid
from asyncio import Queue

from prometheus_client import Gauge

from .singleton import Singleton

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")

class MessageFormat:
    pattern = "{relayer} {uid}"

    def __init__(self, relayer: str, uid: str = None):
        self.relayer = relayer
        self.uid = uid if uid else str(uuid.uuid4())

    @classmethod
    def parse(cls, input_string: str):
        re_pattern = "^" + \
            cls.pattern.replace("{", "(?P<").replace("}", ">.+)") + "$"

        match = re.compile(re_pattern).match(input_string)
        if not match:
            raise ValueError(
                f"Input string format is incorrect. {input_string} incompatible with format {cls.pattern}"
            )
        return cls(match.group("relayer"), match.group("uid"))

    def format(self):
        return self.pattern.format_map(self.__dict__)


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