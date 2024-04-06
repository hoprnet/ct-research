import os

from .baseclass import Base
from .utils import Utils


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

    def from_env(self, *prefixes: list[str]):
        for prefix in prefixes:
            subparams = type(self)()

            subparams_name = prefix.lower()
            if subparams_name[-1] == "_":
                subparams_name = subparams_name[:-1]

            for key, value in Utils.envvarWithPrefix(prefix).items():
                k = key.replace(prefix, "").lower()

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

                setattr(subparams, k, value)

            setattr(self, subparams_name, subparams)

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
