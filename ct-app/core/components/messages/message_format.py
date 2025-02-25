import re
from datetime import datetime


class MessageFormat:
    pattern = "{relayer} {index} {inner_index} {multiplier} {timestamp}"
    index = 0
    range = int(1e5)

    def __init__(self, relayer: str, index: str = None, inner_index: int = None, multiplier: int = None, timestamp: str = None ):
        self.relayer = relayer
        self.index = int(index) if index else self.message_index
        self.timestamp = int(float(timestamp)) if timestamp else int(datetime.now().timestamp()*1000)
        self.multiplier = int(multiplier) if multiplier else 1
        self.inner_index = int(inner_index) if inner_index else 1

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
        return cls(match.group("relayer"), match.group("index"), match.group("inner_index"), match.group("multiplier"), match.group("timestamp"))

    def increase_inner_index(self):
        self.inner_index += 1

    def format(self):
        return self.pattern.format_map(self.__dict__)
    
    def bytes(self):
        return self.format().encode()