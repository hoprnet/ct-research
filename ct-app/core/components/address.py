from typing import Any

from ..api.response_objects import try_to_lower


class Address:
    """
    Class that represents a native address.
    """

    def __init__(self, native: str):
        """
        Create a new Address from a native address.
        :param address: The address of the peer.
        """
        self.native: str | Any = native

    @property
    def native(self) -> str | Any:
        return self._native

    @native.setter
    def native(self, value: str):
        self._native = try_to_lower(value)

    def __eq__(self, other):
        return self.native == other.native

    def __hash__(self):
        return hash(self.native)

    def __repr__(self):
        return f"Address({self.native})"
