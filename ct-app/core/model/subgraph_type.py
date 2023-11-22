from enum import Enum


class SubgraphType(Enum):
    DEFAULT = "default"
    BACKUP = "backup"
    NONE = "None"

    @classmethod
    def callables(cls):
        return [item for item in cls if item != cls.NONE]

    def toInt(self):
        return { SubgraphType.DEFAULT: 0, SubgraphType.BACKUP: 1 }.get(self, -1)
