import re
from typing import Optional


class PatternMatcher:
    def __init__(self, pattern: str, *extras: str):
        self.pattern = pattern
        self.extras = list(extras)

    def search(self, input: str) -> Optional[list[str]]:
        if match := re.search(self.pattern, input):
            return list(match.groups()) + self.extras
        else:
            return None
