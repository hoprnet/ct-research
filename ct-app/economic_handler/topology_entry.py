class TopologyEntry:
    def __init__(self, peer_id: str, node_address: str, channels_balance: int):
        self.peer_id: str = peer_id
        self.node_address = node_address
        self.channels_balance = channels_balance

    @classmethod
    def fromDict(cls, peer_id: str, value: dict):
        return cls(peer_id, value["source_node_address"], value["channels_balance"])

    def __repr__(self):
        return (
            f"TopologyEntry(peer_id={self.peer_id}, "
            + f"node_address={self.node_address}, "
            + f"channels_balance={self.channels_balance})"
        )
