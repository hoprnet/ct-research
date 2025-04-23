import re
from datetime import datetime


class MessageFormat:
    params = ["size", "relayer", "index", "inner_index", "multiplier", "timestamp"]
    range = int(1e5)
    index = 0

    def __init__(
        self,
        size: int,
        relayer: str,
        index: str = None,
        inner_index: int = None,
        multiplier: int = None,
        timestamp: str = None,
    ):
        self.size = int(size)
        self.relayer = relayer
        self.index = int(index) if index else self.message_index
        self.timestamp = (
            int(float(timestamp))
            if timestamp
            else int(datetime.now().timestamp() * 1000)
        )
        self.multiplier = int(multiplier) if multiplier else 1
        self.inner_index = int(inner_index) if inner_index else 1

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
                f"Input string format is incorrect. `{input_string}` incompatible with format {cls.pattern()}"
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

    def __repr__(self):
        return f"{self.__class__.__name__} ({', '.join([f'{param}={getattr(self, param)}' for param in self.params])})"
