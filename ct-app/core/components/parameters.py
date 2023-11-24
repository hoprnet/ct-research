from typing import Any

from .baseclass import Base
from .utils import Utils


class Parameters(Base):
    table = []

    def __init__(self):
        super().__init__()

    def __getattribute__(self, __name: str) -> Any:
        # self.warning(__name)
        self.warning(__name)
        return object.__getattribute__(self, __name)

    def __getattr__(self, item):
        print("__getattr__ " + item)

    def __call__(self, *prefixes: str or list[str]):
        for prefix in prefixes:
            subparams = self.__class__()

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

        return self

    def __str__(self):
        return
