import logging
import os
from types import UnionType
from dataclasses import fields, is_dataclass
from decimal import Decimal
from typing import Any, Optional, Union, get_args, get_origin

from ..types.balance import Balance

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
    @staticmethod
    def _dataclass_fields(target: Any):
        return fields(target)  # type: ignore[arg-type]

    @staticmethod
    def _optional_inner_type(field_type: Any) -> Any:
        origin = get_origin(field_type)
        if origin in {Optional, Union, UnionType}:
            args = [arg for arg in get_args(field_type) if arg is not type(None)]
            if args:
                return args[0]
        return field_type

    @staticmethod
    def _is_dataclass_type(field_type: Any) -> bool:
        return isinstance(field_type, type) and is_dataclass(field_type)

    @classmethod
    def _coerce_list(cls, value: list[Any], field_type: Any) -> list[Any]:
        (item_type,) = get_args(field_type) or (Any,)
        return [cls._coerce_value(v, item_type) for v in value]

    @classmethod
    def _coerce_dict(cls, value: dict[Any, Any], field_type: Any) -> dict[Any, Any]:
        key_type, val_type = get_args(field_type) or (Any, Any)
        return {
            cls._coerce_value(k, key_type): cls._coerce_value(v, val_type) for k, v in value.items()
        }

    @classmethod
    def _coerce_special_scalar(cls, value: Any, field_type: Any) -> Any:
        if field_type is Flag:
            if isinstance(value, Flag):
                return value.value
            return Flag(value)
        if field_type is Duration:
            if isinstance(value, Duration):
                return value.value
            return Duration(value)
        return None

    @classmethod
    def _coerce_value(cls, value: Any, field_type: Any) -> Any:
        if value is None:
            return None
        field_type = cls._optional_inner_type(field_type)
        origin = get_origin(field_type)
        if origin is list:
            return cls._coerce_list(value, field_type)
        if origin is dict:
            return cls._coerce_dict(value, field_type)
        if cls._is_dataclass_type(field_type):
            return field_type(value)
        coerced = cls._coerce_special_scalar(value, field_type)
        if coerced is not None:
            return coerced
        return field_type(value)

    @classmethod
    def _field_is_required(cls, field) -> bool:
        return cls._optional_inner_type(field.type) is not dict

    @classmethod
    def _verify_field_presence(cls, instance: "ExplicitParams", field) -> None:
        if not hasattr(instance, field.name) and cls._field_is_required(field):
            raise KeyError(f"Missing required field: {field.name}")

    @classmethod
    def _verify_field_value(cls, data: dict, field) -> None:
        field_type = cls._optional_inner_type(field.type)
        if cls._is_dataclass_type(field_type):
            field_type.verify(data.get(field.name, {}))
            return
        if not isinstance(field_type, type):
            raise TypeError(f"Expected a dataclass for field {field.name}, got {field.type}")

    @classmethod
    def _default_value_for_type(cls, field_type: Any) -> Any:
        field_type = cls._optional_inner_type(field_type)
        origin = get_origin(field_type)

        if cls._is_dataclass_type(field_type):
            return field_type.generate()
        if origin is list:
            return []
        if origin is dict:
            return {}
        if field_type is Flag:
            return 0
        if field_type is Duration:
            return "0s"
        if field_type is Balance:
            return "0 wxHOPR"
        if field_type is Decimal:
            return 0.0
        if field_type is dict:
            return {}
        return field_type()

    def __init__(self, data: Optional[dict] = None):
        if data is None:
            data = {}

        for f in self._dataclass_fields(type(self)):
            if f.name not in data:
                continue
            value = data[f.name]

            field_type = f.type
            setattr(self, f.name, self._coerce_value(value, field_type))

    def as_dict(self):
        result = {}
        for f in self._dataclass_fields(type(self)):
            if not hasattr(self, f.name):
                continue

            v = getattr(self, f.name)

            if isinstance(v, ExplicitParams):
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

        for field in cls._dataclass_fields(cls):
            cls._verify_field_presence(instance, field)
            cls._verify_field_value(data, field)

        return True

    @classmethod
    def generate(cls) -> dict:
        result = {}
        for field in cls._dataclass_fields(cls):
            result[field.name] = cls._default_value_for_type(field.type)
        return result

    def __repr__(self):
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"
