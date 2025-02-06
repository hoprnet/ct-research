from prometheus_client import Gauge

from core.components.utils import Utils

PEER = Gauge("ct_address_pairs", "PeerID / address pairs of node reachable by CT", ["peer_id", "address"])

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
        self.hopr = hopr
        self.native = Utils.checksum_address(native)
        PEER.labels(self.hopr, self.native).set(1)

    def __eq__(self, other):
        return self.hopr == other.hopr and self.native == other.native

    def __hash__(self):
        return hash((self.hopr, self.native))

    def __repr__(self):
        return f"Address({self.hopr}, {self.native})"
