from enum import Enum


class SubgraphType(Enum):
    DEFAULT = "default"
    BACKUP = "backup"
    NONE = "None"

    def toInt(self):
        return {SubgraphType.DEFAULT: 0, SubgraphType.BACKUP: 1}.get(self, -1)

    @classmethod
    def callables(cls):
        return [item for item in cls if item != cls.NONE]

    @classmethod
    def fromString(cls, type: str):
        return {"default": cls.DEFAULT, "backup": cls.BACKUP}.get(type, cls.NONE)
