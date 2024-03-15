class SubgraphEntry:
    def __init__(
        self,
        nodes: list[str],
        wxHoprBalance: str,
        safe_address: str,
    ):
        self.nodes = nodes
        self.wxHoprBalance = wxHoprBalance
        self.safe_address = safe_address

    @classmethod
    def fromSubgraphResult(cls, nodes: dict):
        safe = nodes[0]["safe"]
        return cls(
            [node["node"]["id"] for node in nodes],
            float(safe["balance"]["wxHoprBalance"]),
            safe["id"],
        )

    def has_address(self, address: str):
        return self.node_address == address

    def __eq__(self, other):
        return (
            self.nodes == other.nodes
            and self.wxHoprBalance == other.wxHoprBalance
            and self.safe_address == other.safe_address
        )

    def __str__(self):
        return (
            f"SubgraphEntry(nodes={self.nodes}, "
            + f"wxHoprBalance={self.wxHoprBalance}, "
            + f"safe_address={self.safe_address}), "
        )

    def __repr__(self):
        return str(self)