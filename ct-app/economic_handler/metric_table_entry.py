from tools.db_connection import NodePeerConnection


class MetricTableEntry:
    def __init__(
        self, peer_id: str, node_ids: list[str], latencies: list[int], timestamp: str
    ):
        self.peer_id: str = peer_id
        self.unordered_node_ids: list[str] = node_ids
        self.unordered_latencies: list[int] = latencies
        self.timestamp: str = timestamp
        self.order: list[int] = None

    @property
    def node_ids(self):
        if self.order is None:
            return self.unordered_node_ids
        if len(self.order) != len(self.unordered_node_ids):
            raise ValueError(
                "temp_order and unordered_latencies must have the same length"
            )
        if sum(self.order) != max(self.order) * (max(self.order) + 1) / 2:
            raise ValueError("order contains non consecutive numbers")

        return [self.unordered_node_ids[i] for i in self.order]

    @property
    def latencies(self):
        if self.order is None:
            return self.unordered_latencies
        if len(self.order) != len(self.unordered_latencies):
            raise ValueError(
                "temp_order and unordered_latencies must have the same length"
            )
        if sum(self.order) != max(self.order) * (max(self.order) + 1) / 2:
            raise ValueError("order contains non consecutive numbers")

        return [self.unordered_latencies[i] for i in self.order]

    @classmethod
    def fromNodePeerConnections(cls, entries: [NodePeerConnection]):
        peer_id = entries[0].peer_id
        node_ids = [entry.node for entry in entries]
        latencies = [entry.latency for entry in entries]
        timestamp = entries[0].timestamp

        return cls(peer_id, node_ids, latencies, timestamp)

    def hasPeerId(self, peer_id: str):
        return self.peer_id == peer_id
