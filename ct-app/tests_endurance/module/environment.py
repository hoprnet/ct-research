import os


class EnvironmentUtils:
    @classmethod
    def envvar(cls, name: str, type=str, default=None):
        value = os.getenv(name)
        if value is None:
            return default

        if type is bool:
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return type(value)
