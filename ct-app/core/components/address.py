class Address:
    """
    Class that represents a native address.
    """

    def __init__(self, native: str):
        """
        Create a new Address from a native address.
        :param address: The address of the peer.
        """
        self.native = native

    @property
    def native(self):
        return self._native

    @native.setter
    def native(self, value: str):
        self._native = value.lower() if value is not None else None

    def __eq__(self, other):
        return self.native == other.native

    def __hash__(self):
        return hash(self.native)

    def __repr__(self):
        return f"Address({self.native})"
