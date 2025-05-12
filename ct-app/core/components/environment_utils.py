import os
from typing import Any


class EnvironmentUtils:
    @classmethod
    def envvarWithPrefix(cls, prefix: str, type=str) -> dict[str, Any]:
        """
        Retrieves environment variables with a specified prefix and converts their values.
        
        Args:
            prefix: The prefix to filter environment variable names.
            type: The type to which each variable's value will be converted (default: str).
        
        Returns:
            A dictionary of environment variables whose names start with the given prefix,
            with values converted to the specified type and sorted by key.
        """
        var_dict = {key: type(v) for key, v in os.environ.items() if key.startswith(prefix)}

        return dict(sorted(var_dict.items()))

    @classmethod
    def envvar(cls, name: str, default: str = None, type=str) -> Any:
        return type(os.environ.get(name, default))
