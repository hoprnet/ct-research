import logging
import os
from dataclasses import fields, is_dataclass
from decimal import Decimal
from typing import Any, Optional, Union, get_args, get_origin

from ..balance import Balance
from ..logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class Flag:
    def __init__(self, value: object):
        self.value = self._parse(value)

    def _parse(self, value: object) -> object:
        if isinstance(value, Flag):
            return value.value
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value.strip()
            lowered = text.lower()
            if lowered in {"on", "true", "yes"}:
                return True
            if lowered in {"off", "false", "no"}:
                return False

        try:
            return Duration(value).value
        except TypeError as exc:
            raise TypeError(f"Flag value must be a duration or On/Off, got {type(value)}") from exc


class Duration:
    def __init__(self, value: object):
        self.value = self._parse(value)

    def _parse(self, value: object) -> float:
        if isinstance(value, Duration):
            return value.value
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            units = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
            num = ""
            unit = ""
            for ch in text:
                if ch.isdigit() or ch == ".":
                    num += ch
                elif not ch.isspace():
                    unit += ch
            if num:
                try:
                    value_num = float(num)
                except ValueError as exc:
                    raise TypeError(f"Duration value must be a number, got {value!r}") from exc
                if not unit:
                    return value_num
                unit = unit.lower()
                if unit in units:
                    return value_num * units[unit]
                raise TypeError(f"Unknown duration unit '{unit}' in {value!r}")
        raise TypeError(f"Duration value must be a duration string or number, got {type(value)}")

    def __repr__(self):
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"


class ExplicitParams:
    def _coerce_value(self, value: Any, field_type: Any) -> Any:
        if value is None:
            return None
        origin = get_origin(field_type)
        if origin is list:
            (item_type,) = get_args(field_type) or (Any,)
            return [self._coerce_value(v, item_type) for v in value]
        if origin is dict:
            key_type, val_type = get_args(field_type) or (Any, Any)
            return {
                self._coerce_value(k, key_type): self._coerce_value(v, val_type)
                for k, v in value.items()
            }
        if origin is Optional or origin is Union:
            args = [arg for arg in get_args(field_type) if arg is not type(None)]
            if not args:
                return value
            return self._coerce_value(value, args[0])
        if is_dataclass(field_type):
            return field_type(value)
        if field_type is Flag:
            if isinstance(value, Flag):
                return value.value
            return Flag(value)
        if field_type is Duration:
            if isinstance(value, Duration):
                return value.value
            return Duration(value)
        return field_type(value)

    def __init__(self, data: Optional[dict] = None):
        if data is None:
            data = {}

        for f in fields(self):
            if f.name not in data:
                continue
            value = data[f.name]

            field_type = f.type
            setattr(self, f.name, self._coerce_value(value, field_type))

    def as_dict(self):
        result = {}
        for f in fields(self):
            if not hasattr(self, f.name):
                continue

            v = getattr(self, f.name)

            if is_dataclass(v):
                result[f.name] = v.as_dict()
            else:
                result[f.name] = self._coerce_value(v, f.type)
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
            field_type = field.type
            origin = get_origin(field_type)
            if origin is Optional or origin is Union:
                args = [arg for arg in get_args(field_type) if arg is not type(None)]
                field_type = args[0] if args else field_type
                origin = get_origin(field_type)

            if is_dataclass(field_type):
                result[field.name] = field_type.generate()  # ty: ignore[possibly-missing-attribute]
            elif origin is list:
                result[field.name] = []
            elif origin is dict:
                result[field.name] = {}
            else:
                if field_type is Flag:
                    result[field.name] = 0
                elif field_type is Duration:
                    result[field.name] = "0s"
                elif field_type is Balance:
                    result[field.name] = "0 wxHOPR"
                elif field_type is Decimal:
                    result[field.name] = 0.0
                elif field_type is dict:
                    result[field.name] = {}
                else:
                    result[field.name] = field_type()
        return result

    def __repr__(self):
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"
