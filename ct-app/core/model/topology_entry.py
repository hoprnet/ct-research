from .peer import Peer


class TopologyEntry:
    """
    Class that represents a single topology entry (from the API).
    """

    def __init__(self, peer_id: str, node_address: str, channels_balance: int):
        """
        Create a new TopologyEntry with the specified peer_id, node_address and channels_balance.
        :param peer_id: The peer's peerId.
        :param node_address: The peer's native address.
        :param channels_balance: The peer's outgoing channels total balance.
        """
        self.peer_id: str = peer_id
        self.node_address = node_address
        self.channels_balance = channels_balance

    @classmethod
    def fromDict(cls, peer_id: str, value: dict):
        """
        Create a new TopologyEntry from the specified dictionary.
        :param peer_id: The peer's peerId.
        :param value: The dictionary to create the TopologyEntry from.
        """

        return cls(peer_id, value["source_node_address"], value["channels_balance"])

    def __repr__(self):
        return (
            f"TopologyEntry(peer_id={self.peer_id}, "
            + f"node_address={self.node_address}, "
            + f"channels_balance={self.channels_balance})"
        )

    def to_peer(self) -> Peer:
        peer = Peer(self.peer_id, self.node_address, "v0.0.0")
        peer.channel_balance = self.channels_balance
        return peer
