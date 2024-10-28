import re
from asyncio import Queue
from datetime import datetime
from typing import Union

from prometheus_client import Gauge

from .singleton import Singleton

queue_size = Gauge("ct_queue_size", "Size of the message queue")


class MessageQueue(metaclass=Singleton):
    def __init__(self):
        self._buffer = Queue()

    @property
    def buffer(self):
        queue_size.set(self._buffer.qsize())
        return self._buffer

    @classmethod
    def clear(cls):
        instance = cls()

        while not instance._buffer.empty():
            instance._buffer.get_nowait()
            instance._buffer.task_done()


class MessageFormat:
    pattern = "{relayer} at {timestamp}"

    def __init__(self, relayer: str, timestamp: Union[str, datetime]):
        self.relayer = relayer
        if isinstance(timestamp, str):
            self.timestamp = datetime.fromisoformat(timestamp)
        else:
            self.timestamp = timestamp

    @classmethod
    def parse(cls, input_string):
        re_pattern = "^" + cls.pattern.replace("{", "(?P<").replace("}", ">.+)") + "$"

        match = re.compile(re_pattern).match(input_string)
        if not match:
            raise ValueError(
                f"Input string format is incorrect. {input_string} incompatible with format {cls.pattern}"
            )
        return cls(match.group("relayer"), match.group("timestamp"))

    def format(self):
        return self.pattern.format_map(self.__dict__)
