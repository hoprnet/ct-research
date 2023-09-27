import time
from .address import Address


class Peer:
    def __init__(
        self,
        address: Address,
        value: int = None,
        timestamp: float = None,
        transmit: bool = False,
    ):
        """
        Initialisation of the class.
        """
        self.address = address
        self._value = value
        self.timestamp = timestamp
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

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: int or None):
        self._value = value

        if value is not None:
            self.timestamp = time.time()
            self.transmit = True
        else:
            self.transmit = False
