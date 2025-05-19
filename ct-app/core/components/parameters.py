import logging

from core.components.logs import configure_logging

from .environment_utils import EnvironmentUtils as Utils

configure_logging()
logger = logging.getLogger(__name__)


class Parameters:
    """
    Class that represents a set of parameters that can be accessed and modified. The parameters are
    stored in a dictionary and can be accessed and modified using the dot notation.
    The parameters can be loaded from environment variables with a specified prefix.
    """

    def __init__(self):
        super().__init__()

    def parse(self, data: dict, entrypoint=False):
        for key, value in data.items():
            subparams = type(self)()
            key = key.replace("-", "_")

            setattr(self, key, subparams)
            if isinstance(value, dict):
                subparams.parse(value)
            else:
                setattr(self, key, value)

        if entrypoint:
            logger.debug("Loaded config from file", {"config": self.as_dict})

    def overrides(self, prefix: str):
        for key, value in Utils.envvarWithPrefix(prefix).items():
            path = key.replace(prefix, "").lower().split("_")
            parent = self

            for p in path:
                raw_attrs = dir(parent)
                attrs = list(map(lambda str: str.lower(), raw_attrs))

                if p.lower() in attrs:
                    param_name = raw_attrs[attrs.index(p)]
                    child = getattr(parent, param_name)

                    if isinstance(child, type(self)):
                        parent = child
                    else:
                        setattr(parent, param_name, self._convert(value))
                else:
                    raise KeyError(f"Key {key} not found in parameters")

    def from_env(self, *prefixes: str):
        for prefix in prefixes:
            subparams_name = prefix.lower().strip("_")
            raw_attrs: list[str] = dir(self)
            attrs = list(map(lambda str: str.lower(), raw_attrs))

            if subparams_name in attrs:
                subparams = getattr(self, raw_attrs[attrs.index(subparams_name)])
            else:
                subparams = type(self)()

            self._parse_env_vars(prefix, subparams)

            setattr(self, subparams_name, subparams)

    def _parse_env_vars(self, prefix, subparams):
        for key, value in Utils.envvarWithPrefix(prefix).items():
            k = self._format_key(key, prefix)
            value = self._convert(value)
            setattr(subparams, k, value)

    def _format_key(self, key, prefix):
        k = key.replace(prefix, "").lower()
        k = k.replace("_", " ").title().replace(" ", "")
        k = k[0].lower() + k[1:]
        return k

    def _convert(self, value: str) -> str | int | float:
        try:
            value: float = float(value)
        except ValueError:
            pass

        try:
            integer: int = int(value)
            if integer == value:
                value: int = integer

        except ValueError:
            pass

        return value

    @property
    def as_dict(self):
        return {k: v.as_dict if isinstance(v, type(self)) else v for k, v in self.__dict__.items()}

    def __repr__(self):
        return str(self.__dict__)
