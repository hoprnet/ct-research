class SubgraphEntry:
    def __init__(self, node_address: str, wxHoprBalance: str, safe_address: str):
        self.node_address = node_address
        self.wxHoprBalance = wxHoprBalance
        self.safe_address = safe_address

    @classmethod
    def fromSubgraphResult(cls, node: dict):
        return cls(
            node["node"]["id"], node["node"]["wxHoprBalance"], node["safe"]["id"]
        )

    def hasAddress(self, address: str):
        return self.node_address == address
