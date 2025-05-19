import os
from typing import Any, Optional


class EnvironmentUtils:
    @classmethod
    def envvarWithPrefix(cls, prefix: str, type=str) -> dict[str, Any]:
        var_dict = {key: type(v) for key, v in os.environ.items() if key.startswith(prefix)}

        return dict(sorted(var_dict.items()))

    @classmethod
    def envvar(cls, name: str, default: Optional[Any] = None, type=str) -> Any:
        return type(os.environ.get(name, default))
