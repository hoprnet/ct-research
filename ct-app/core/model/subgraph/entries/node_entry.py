from .entry import SubgraphEntry
from .safe_entry import SafeEntry


class NodeEntry(SubgraphEntry):
    """
    A NodeEntry represents a single entry in the subgraph.
    """

    def __init__(self, address: str, safe: SafeEntry):
        """
        Create a new NodeEntry.
        :param address: The address of the node.
        :param wxHoprBalance: The wxHoprBalance of the node.
        :param safe: A SafeEntry object.
        """

        self.address = address
        self.safe = safe

    @classmethod
    def fromSubgraphResult(cls, node: dict):
        """
        Create a new NodeEntry from the specified subgraph result.
        :param node: The subgraph result to create the NodeEntry from.
        """
        return cls(
            node["node"]["id"],
            SafeEntry.fromSubgraphResult(node["safe"]),
        )
