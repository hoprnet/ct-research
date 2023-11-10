from enum import Enum


class SubgraphType(Enum):
    DEFAULT = "default"
    BACKUP = "backup"
    NONE = "None"

    @classmethod
    def callables(cls):
        return [item for item in cls if item != cls.NONE]

    def toInt(self):
        if self == SubgraphType.DEFAULT:
            return 0
        if self == SubgraphType.BACKUP:
            return 1
        return -1
