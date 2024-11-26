from enum import Enum, unique


@unique
class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"

    @classmethod
    def fromStr(cls, protocol: str):
        return getattr(cls, protocol.upper())
