from .entry import SubgraphEntry
from .safe_entry import SafeEntry


class AllocationEntry(SubgraphEntry):
    def __init__(self, id: str, claimedAmount: str, allocatedAmount: str):
        self.address = id
        self.claimedAmount = float(claimedAmount) / 1e18
        self.allocatedAmount = float(allocatedAmount) / 1e18
        self.linked_safes: list[SafeEntry] = []

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)
