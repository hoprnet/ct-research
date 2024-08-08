from .entry import SubgraphEntry


class AllocationEntry(SubgraphEntry):
    def __init__(self, id: str, claimedAmount: str, allocatedAmount: str):
        self.address = id
        self.claimedAmount = float(claimedAmount) / 1e18
        self.allocatedAmount = float(allocatedAmount) / 1e18
