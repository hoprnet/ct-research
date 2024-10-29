from .entry import SubgraphEntry
from .safe import Safe


class Allocation(SubgraphEntry):
    def __init__(self, id: str, claimedAmount: str, allocatedAmount: str):
        self.address = id
        self.claimed_amount = float(claimedAmount) / 1e18
        self.allocated_amount = float(allocatedAmount) / 1e18
        self.linked_safes: set[Safe] = set()

    @property
    def unclaimed_amount(self):
        return self.allocated_amount - self.claimed_amount

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)
