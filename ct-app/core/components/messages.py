import re
from asyncio import Queue
from datetime import datetime

from prometheus_client import Gauge

from .singleton import Singleton

QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")


class MessageFormat:
    pattern = "{relayer} {index} {timestamp}"
    index = 0
    range = int(1e10)

    def __init__(self, relayer: str, index: str = None, timestamp: str = None):
        self.relayer = relayer
        self.timestamp = int(float(timestamp)) if timestamp else int(
            datetime.now().timestamp()*1000)
        self.index = int(index) if index else self.message_index

    @property
    def message_index(self):
        value = self.__class__.index
        self.__class__.index += 1
        self.__class__.index %= (self.__class__.range)
        return value

    @classmethod
    def parse(cls, input_string: str):
        re_pattern = "^" + \
            cls.pattern.replace("{", "(?P<").replace("}", ">.+)") + "$"

        match = re.compile(re_pattern).match(input_string)
        if not match:
            raise ValueError(
                f"Input string format is incorrect. {input_string} incompatible with format {cls.pattern}"
            )
        return cls(match.group("relayer"), match.group("index"), match.group("timestamp"))

    def format(self):
        return self.pattern.format_map(self.__dict__)

    def bytes(self):
        return self.format().encode()


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
