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

    @property
    def segment(self):
        return False

    @property
    def retransmit(self):
        return False
