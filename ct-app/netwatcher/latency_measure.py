import time
from .peer import Peer


class LatencyMeasure:
    def __init__(
        self,
        value: int,
        timestamp: float,
        node: Peer,
        transmit: bool = False,
    ):
        """
        Initialisation of the class.
        """
        self.value = value
        self.timestamp = timestamp
        self.node = node
        self._transmit = transmit

    @property
    def transmit(self) -> bool:
        if self._transmit:
            return True

        if time.time() - self.timestamp > 60 * 60 * 2 and self.value is not None:
            self.value = -1
            return True

        return False

    @transmit.setter
    def transmit(self, value: bool):
        self._transmit = value

    @property
    def close_channel(self) -> bool:
        return time.time() - self.timestamp > 60 * 60 * 24
