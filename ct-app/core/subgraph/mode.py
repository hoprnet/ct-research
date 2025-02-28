from enum import Enum


class Mode(Enum):
    DEFAULT = "default"
    BACKUP = "backup"
    NONE = "None"

    def to_int(self):
        return {Mode.DEFAULT: 0, Mode.BACKUP: 1}.get(self, -1)

    @classmethod
    def callables(cls):
        return [item for item in cls if item != cls.NONE]

    @classmethod
    def fromString(cls, mode: str):
        return {"default": cls.DEFAULT, "backup": cls.BACKUP}.get(mode, cls.NONE)
