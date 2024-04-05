import os

from .baseclass import Base


class Parameters(Base):
    def __init__(self):
        super().__init__()

    def parse(self, data: dict):
        for key, value in data.items():
            subparams = type(self)()
            key: str = key.replace("-", "_")

            setattr(self, key, subparams)
            if isinstance(value, dict):
                subparams.parse(value)
            else:
                if v := os.environ.get(f"OVERRIDE_{key.upper()}", None):
                    value = self._convert(v)
                setattr(self, key, value)

    def _convert(self, value: str):
        try:
            value = float(value)
        except ValueError:
            pass

        try:
            integer = int(value)
            if integer == value:
                value = integer

        except ValueError:
            pass

        return value

    def __str__(self):
        return
