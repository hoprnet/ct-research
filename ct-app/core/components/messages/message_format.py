import re
from datetime import datetime
from typing import Optional


class MessageFormat:
    params = [
        "packet_size",
        "relayer",
        "sender",
        "index",
        "inner_index",
        "multiplier",
        "timestamp",
    ]
    range = int(1e5)
    index = 0

    def __init__(
        self,
        packet_size: int,
        relayer: str,
        sender: str = None,
        index: str = None,
        inner_index: int = None,
        multiplier: int = None,
        timestamp: str = None,
    ):
        self.packet_size = int(packet_size)
        self.sender = sender
        self.relayer = relayer
        self.index = int(index) if index else self.message_index
        self.update_timestamp(timestamp)
        self.multiplier = int(multiplier) if multiplier else 1
        self.inner_index = int(inner_index) if inner_index else 1

    @property
    def size(self):
        return self.packet_size * self.multiplier

    @property
    def message_index(self):
        value = self.__class__.index
        self.__class__.index += 1
        self.__class__.index %= self.__class__.range
        return value

    @classmethod
    def pattern(self):
        return " ".join([f"{{{param}}}" for param in self.params])

    @classmethod
    def parse(cls, input_string: str):
        if len(input_string) == 0:
            raise ValueError("Input string is empty")

        re_pattern = "^" + cls.pattern().replace("{", "(?P<").replace("}", ">.+)") + "$"

        match = re.compile(re_pattern).match(input_string)
        if not match:
            raise ValueError(
                f"Input string format is incorrect. `{input_string}`"
                + "incompatible with format {cls.pattern()}"
            )

        return cls(*[match.group(param) for param in cls.params])

    def increase_inner_index(self):
        self.inner_index += 1

    def format(self):
        return self.pattern().format_map(self.__dict__)

    def bytes(self):
        message_as_bytes = self.format().encode()

        if len(message_as_bytes) > self.size:
            raise ValueError(
                f"Encoded message is exceeds specified size ({len(message_as_bytes)} > {self.size})"
            )
        return message_as_bytes + b"\0" * (self.size - len(message_as_bytes))

    def update_timestamp(self, timestamp: Optional[str] = None):
        if timestamp is not None:
            self.timestamp = int(float(timestamp))
        else:
            self.timestamp = int(datetime.now().timestamp() * 1000)

    def __eq__(self, other):
        if not isinstance(other, MessageFormat):
            return False
        return all(getattr(self, param) == getattr(other, param) for param in self.params)

    def __repr__(self):
        attrs_as_strs = [f"{param}={getattr(self, param)}" for param in self.params]
        return f"{self.__class__.__name__}({', '.join(attrs_as_strs)})"
