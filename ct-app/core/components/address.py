class Address:
    """
    Class that represents an address with a native and native address.
    """

    def __init__(self, hopr: str, native: str):
        """
        Create a new Address with the specified id and address. The `hopr` refers the the peerId, and the `native` refers to the native address of a node.
        :param id: The id of the peer.
        :param address: The address of the peer.
        """
        self.hopr = hopr.lower() if isinstance(hopr, str) else hopr
        self.native = native.lower() if isinstance(native, str) else native

    def __eq__(self, other):
        return self.hopr == other.hopr and self.native == other.native

    def __hash__(self):
        return hash((self.hopr, self.native))

    def __repr__(self):
        return f"Address({self.hopr}, {self.native})"
