from prometheus_client import Gauge

PEER = Gauge(
    "ct_address_pairs",
    "PeerID / address pairs of node reachable by CT",
    ["peer_id", "address"],
)


class Address:
    """
    Class that represents an address with a native and native address.
    """

    def __init__(self, hopr: str, native: str):
        """
        Create a new Address with the specified id and address. The `hopr` refers the the peerId,
        and the `native` refers to the native address of a node.
        :param id: The id of the peer.
        :param address: The address of the peer.
        """
        self.hopr = hopr
        self.native = native
        PEER.labels(self.hopr, self.native).set(1)

    @property
    def hopr(self):
        return self._hopr

    @hopr.setter
    def hopr(self, value: str):
        self._hopr = value

    @property
    def native(self):
        return self._native

    @native.setter
    def native(self, value: str):
        self._native = value.lower() if value is not None else None

    def __eq__(self, other):
        return self.hopr == other.hopr and self.native == other.native

    def __hash__(self):
        return hash((self.hopr, self.native))

    def __repr__(self):
        return f"Address({self.hopr}, {self.native})"
