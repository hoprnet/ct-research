class Address:
    """
    Class that represents an address with an id and an address.
    """

    def __init__(self, id: str, address: str):
        """
        Create a new Address with the specified id and address. The `id` refers the the peerId, and the `address` refers to the native address of a node.
        :param id: The id of the peer.
        :param address: The address of the peer.
        """
        self.id = id
        self.address = address

    def __eq__(self, other):
        return self.id == other.id and self.address == other.address

    def __hash__(self):
        return hash((self.id, self.address))

    def __repr__(self):
        return f"Address({self.id}, {self.address})"
