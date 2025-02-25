import re
from datetime import datetime


class MessageFormat:
    pattern = "{relayer} {index} {timestamp}"
    index = 0
    range = int(1e10)

    def __init__(self, relayer: str, index: str = None, timestamp: str = None):
        self.relayer = relayer
        self.timestamp = int(float(timestamp)) if timestamp else int(datetime.now().timestamp()*1000)
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
