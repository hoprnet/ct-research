class ExplicitParams:
    keys: dict[str, type] = {}

    def __init__(self, data: dict = None):
        if data is None:
            data = {}
        self.parse(data)

    def parse(self, data: dict):
        for name, type in self.keys.items():
            if value := data.get(name):
                value = type(value)
                if type is Flag:
                    value = value.value
            setattr(self, name, value)

    @property
    def as_dict(self):
        return {
            k: v.as_dict if isinstance(v, ExplicitParams) else v for k, v in self.__dict__.items()
        }

    @classmethod
    def generate(cls):
        """
        Generate an example representation of the input parameter file.
        """
        example = {}
        for name, _type in cls.keys.items():
            if issubclass(_type, ExplicitParams):
                example[name] = _type().generate()
            elif _type is Flag:
                example[name] = Flag(0).value
            else:
                example[name] = _type()
        return example

    @classmethod
    def verify(cls, data: dict, parent: str = ""):
        """
        Recursively verify all parameters in the input data.
        Returns an instance of the class if all parameters are valid.
        """
        for name, _type in cls.keys.items():
            if hasattr(_type, "verify"):
                _type.verify(data[name], f"{parent}.{name}")
            else:
                if _type is dict:
                    continue

                try:
                    _ = data[name]
                except KeyError:
                    raise KeyError(f"Missing required parameter `{name}` in {parent}")

                if not data[name]:
                    continue

                try:
                    _ = _type(data[name])
                except ValueError:
                    raise ValueError(f"Invalid type for `{name}` in {parent}")

        return cls(data)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_dict})"


class Flag:
    def __init__(self, value: int):
        self.value = value
