from os import environ
from typing import Any

from .baseclass import Base


class EnvironmentUtils(Base):
    @property
    def print_prefix(self) -> str:
        return "EnvUtils"

    @classmethod
    def envvar(cls, var_name: str, default: Any = None, type: type = str):
        if var_name in environ:
            return type(environ[var_name])
        else:
            return default

    @classmethod
    def envvarWithPrefix(cls, prefix: str, type=str) -> dict[str, Any]:
        var_dict = {
            key: type(v) for key, v in environ.items() if key.startswith(prefix)
        }

        return dict(sorted(var_dict.items()))