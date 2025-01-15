from .entry import SubgraphEntry


class Topology(SubgraphEntry):
    """
    Class that represents a single topology entry (from the API).
    """

    def __init__(self, peer_id: str, address: str, channels_balance: int):
        """
        Create a new Topology with the specified peer_id, address and channels_balance.
        :param peer_id: The peer's peerId.
        :param address: The peer's native address.
        :param channels_balance: The peer's outgoing channels total balance.
        """
        self.peer_id: str = peer_id
        self.address = address.lower() if isinstance(address, str) else address
        self.channels_balance = channels_balance

    @classmethod
    def fromDict(cls, peer_id: str, value: dict):
        """
        Create a new Topology from the specified dictionary.
        :param peer_id: The peer's peerId.
        :param value: The dictionary to create the Topology from.
        """

        return cls(peer_id, value["source_node_address"], value["channels_balance"])
