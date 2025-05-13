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

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_dict})"


class Flag:
    def __init__(self, value: int):
        self.value = value
