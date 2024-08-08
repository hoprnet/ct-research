from .entry import SubgraphEntry


class TopologyEntry(SubgraphEntry):
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
