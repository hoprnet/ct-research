from enum import Enum


class ProtocolTemplate:
    def __init__(self, retransmit: bool, segment: bool, no_delay: bool):
        self.retransmit = retransmit
        self.segment = segment
        self.no_delay = no_delay


class Protocol(Enum):
    TCP = ProtocolTemplate(retransmit=False, segment=True, no_delay=False)
    UDP = ProtocolTemplate(retransmit=False, segment=True, no_delay=False)

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
