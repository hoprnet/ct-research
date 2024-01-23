import subprocess
from os import environ
from typing import Any

from .baseclass import Base


class EnvironmentUtils(Base):
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

    @classmethod
    def checkRequiredEnvVar(cls, folder: str):
        result = subprocess.run(
            f"sh ./scripts/list_required_parameters.sh {folder}".split(),
            capture_output=True,
            text=True,
        ).stdout

        all_set_flag = True
        for var in result.splitlines():
            exists = var in environ
            all_set_flag *= exists

            # print var with a leading check mark if it exists or red X (emoji) if it doesn't
            cls().info(f"{'✅' if exists else '❌'} {var}")

        if not all_set_flag:
            cls().error("Some required environment variables are not set.")
        return all_set_flag
