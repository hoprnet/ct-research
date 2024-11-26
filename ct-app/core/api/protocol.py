from enum import Enum, unique


@unique
class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"

    @classmethod
    def fromString(cls, protocol: str):
        try:
            return getattr(cls, protocol.upper())
        except AttributeError:
            raise ValueError(
                f"Invalid protocol: {protocol}. Valid values are: {[p.name for p in cls]}"
            )
