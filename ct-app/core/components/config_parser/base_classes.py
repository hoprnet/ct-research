from dataclasses import fields, is_dataclass
from decimal import Decimal
from typing import Optional, get_args, get_origin

from core.components.balance import Balance


class Flag:
    def __init__(self, value: float):
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
                result[f.name] = f.type(v)
        return result

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
                        f"Expected a dataclass for field {field.name}, got {type(field.type)}"
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
                result[field.name] = field.type.generate()  # ty: ignore[possibly-unbound-attribute]
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
        print(f"{vars(self).keys()=}")
        key_pair_string: str = ", ".join([f"{key}={value}" for key, value in vars(self).items()])
        return f"{self.__class__.__name__}({key_pair_string})"
