
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
            k: v.as_dict if isinstance(v, ExplicitParams) else v
            for k, v in self.__dict__.items()
        }

    def __repr__(self):
        return f"{self.__class__.__name__}({self.as_dict})"


class Flag:
    def __init__(self, value: int):
        self.value = value
