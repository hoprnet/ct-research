from .entry import SubgraphEntry
from .safe_entry import SafeEntry


class NodeEntry(SubgraphEntry):
    """
    A NodeEntry represents a single entry in the subgraph.
    """

    def __init__(self, node_address: str, safe: SafeEntry):
        """
        Create a new NodeEntry with the specified node_address, wxHoprBalance, safe_address and safe_allowance.
        :param node_address: The address of the node.
        :param wxHoprBalance: The wxHoprBalance of the node.
        :param safe_address: The address of the safe.
        :param safe_allowance: The wxHoprAllowance of the safe.
        :param owners: The owners' addresses.
        """

        self.node_address = node_address
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
