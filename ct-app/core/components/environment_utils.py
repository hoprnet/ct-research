import os
from typing import Any

from .baseclass import Base


class EnvironmentUtils(Base):
    @classmethod
    def envvarWithPrefix(cls, prefix: str, type=str) -> dict[str, Any]:
        var_dict = {
            key: type(v) for key, v in os.environ.items() if key.startswith(prefix)
        }

        return dict(sorted(var_dict.items()))

    @classmethod
    def envvar(cls, name: str, default: str = None, type=str) -> Any:
        return type(os.environ.get(name, default))
