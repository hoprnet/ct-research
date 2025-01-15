from .entry import SubgraphEntry
from .safe import Safe


class Node(SubgraphEntry):
    """
    A Node represents a single entry in the subgraph.
    """

    def __init__(self, address: str, safe: Safe):
        """
        Create a new Node.
        :param address: The address of the node.
        :param safe: A Safe object.
        """

        self.address = address if isinstance(address, str) else address
        self.safe = safe

    @classmethod
    def fromSubgraphResult(cls, node: dict):
        """
        Create a new Node from the specified subgraph result.
        :param node: The subgraph result to create the Node from.
        """
        return cls(
            node["node"]["id"].lower(),
            Safe.fromSubgraphResult(node["safe"]),
        )
