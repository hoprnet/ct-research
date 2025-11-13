import logging
import os
from dataclasses import fields, is_dataclass
from decimal import Decimal
from typing import Optional

from ..balance import Balance
from ..logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class Flag:
    def __init__(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Flag value must be an int or float, got {type(value)}")

        self.value = value

    def __repr__(self):
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"


class ExplicitParams:
    def __init__(self, data: Optional[dict] = None):
        if data is None:
            data = {}

        for f in fields(self):
            if f.name not in data:
                continue
            value = data[f.name]

            field_type = f.type
            # Handle nested dataclasses
            if is_dataclass(field_type):
                value = field_type(value)
            # Handle Flag
            elif field_type is Flag:
                value = Flag(value)
            else:
                value = field_type(value)
            setattr(self, f.name, value)

    def as_dict(self):
        result = {}
        for f in fields(self):
            if not hasattr(self, f.name):
                continue

            v = getattr(self, f.name)

            if is_dataclass(v):
                result[f.name] = v.as_dict()
            else:
                result[f.name] = f.type(v)  # ty: ignore[call-non-callable]
        return result

    def set_attribute_from_env(self, attribute: str, env_var: str) -> bool:
        """
        Set the value of an attribute from an environment variable.
        """
        cls_name = self.__class__.__name__
        if not hasattr(self, attribute):
            raise AttributeError(f"{cls_name} has no attribute '{attribute}'")

        if value := os.getenv(env_var):
            setattr(self, attribute, value)
            logger.debug(f"{env_var} key loaded to {cls_name}.{attribute}")

            return True
        else:
            if getattr(self, attribute) == "None":
                raise AttributeError(f"{cls_name}.{attribute} not set and {env_var} key not found.")
            else:
                logger.warning(
                    f"{env_var} key not found, using default value for {cls_name}.{attribute}"
                )
            return False

    @classmethod
    def verify(cls, data: dict) -> bool:
        instance = cls(data)

        for field in instance.__dataclass_fields__.values():
            if not hasattr(instance, field.name):
                if field.type is not dict:
                    raise KeyError(f"Missing required field: {field.name}")

            if not is_dataclass(field.type):
                if not isinstance(field.type, type):
                    raise TypeError(
                        f"Expected a dataclass for field {field.name}, got {field.type}"
                    )
            else:
                field.type.verify(data.get(field.name, {}))

        return True

    @classmethod
    def generate(cls) -> dict:
        instance = cls()
        result = {}
        for field in fields(instance):
            if is_dataclass(field.type):
                result[field.name] = field.type.generate()  # ty: ignore[possibly-missing-attribute]
            elif isinstance(field.type, list):
                result[field.name] = [v.generate() if is_dataclass(v) else v for v in field.type()]
            elif isinstance(field.type, dict):
                result[field.name] = {
                    k: v.generate() if is_dataclass(v) else v for k, v in field.type().items()
                }
            else:
                if field.type is Flag:
                    result[field.name] = 0
                elif field.type is Balance:
                    result[field.name] = "0 wxHOPR"
                elif field.type is Decimal:
                    result[field.name] = 0.0
                elif field.type is dict:
                    result[field.name] = {}
                else:
                    result[field.name] = field.type()
        return result

    def __repr__(self):
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"
