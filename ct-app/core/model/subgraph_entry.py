class SubgraphEntry:
    def __init__(
        self,
        node_address: str,
        wxHoprBalance: str,
        safe_address: str,
        safe_allowance: str,
    ):
        self.node_address = node_address
        self.wxHoprBalance = wxHoprBalance
        self.safe_address = safe_address
        self.safe_allowance = safe_allowance

    @classmethod
    def fromSubgraphResult(cls, node: dict):
        return cls(
            node["node"]["id"],
            node["safe"]["balance"]["wxHoprBalance"],
            node["safe"]["id"],
            node["safe"]["allowance"]["wxHoprAllowance"],
        )

    def has_address(self, address: str):
        return self.node_address == address

    def __eq__(self, other):
        return (
            self.node_address == other.node_address
            and self.wxHoprBalance == other.wxHoprBalance
            and self.safe_address == other.safe_address
            and self.safe_allowance == other.safe_allowance
        )

    def __str__(self):
        return (
            f"SubgraphEntry(node_address={self.node_address}, "
            + f"wxHoprBalance={self.wxHoprBalance}, "
            + f"safe_address={self.safe_address}), "
            + f"safe_allowance={self.safe_allowance})"
        )

    def __repr__(self):
        return str(self)
