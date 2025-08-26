import enum


class Protocol(enum.Enum):
    TCP = "tcp"
    UDP = "udp"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for status in cls:
                if status.value == value:
                    return status

            return cls.Unknown

        return super()._missing_(value)

    def __repr__(self):
        return f"<Protocol.{self.name}>"
