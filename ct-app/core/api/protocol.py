from enum import Enum


class ProtocolTemplate:
    def __init__(self, retransmit: bool, segment: bool, no_delay: bool):
        self.retransmit = retransmit
        self.segment = segment
        self.no_delay = no_delay


class TCPProtocol(ProtocolTemplate):
    def __init__(self):
        super().__init__(retransmit=True, segment=True, no_delay=True)


class UDPProtocol(ProtocolTemplate):
    def __init__(self):
        super().__init__(retransmit=False, segment=True, no_delay=True)


class Protocol(Enum):
    TCP = TCPProtocol()
    UDP = UDPProtocol()

    @classmethod
    def fromString(cls, protocol: str):
        try:
            return getattr(cls, protocol.upper())
        except AttributeError:
            raise ValueError(
                f"Invalid protocol: {protocol}. Valid values are: {[p.name for p in cls]}"
            )

    @property
    def segment(self):
        return self.value.segment

    @property
    def retransmit(self):
        return self.value.retransmit

    @property
    def no_delay(self):
        return self.value.no_delay

    def __eq__(self, other):
        if isinstance(other, str):
            return other.lower() == self.name.lower()

        return self.name == other.name
