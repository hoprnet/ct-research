import time
from .address import Address


class Peer:
    def __init__(
        self,
        address: Address,
        latency: int = None,
        timestamp: float = None,
        transmit: bool = False,
    ):
        self.address = address
        self._latency = latency
        self.timestamp = timestamp
        self._transmit = transmit

    @property
    def transmit(self) -> bool:
        if not self.timestamp:
            return False

        if not self.latency:
            return False

        if self._transmit:
            return True

        if time.time() - self.timestamp > 60 * 60 * 2:
            self.latency = -1

        return True

    @transmit.setter
    def transmit(self, value: bool):
        self._transmit = value

    @property
    def close_channel(self) -> bool:
        if not self.timestamp:
            return False

        return time.time() - self.timestamp > 60 * 60 * 24

    @property
    def latency(self) -> int:
        return self._latency

    @latency.setter
    def latency(self, value: int or None):
        self._latency = value

        self.transmit = value is not None

        if value is not None:
            self.timestamp = time.time()
