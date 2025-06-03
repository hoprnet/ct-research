from core.components.balance import Balance

from .entry import SubgraphEntry
from .safe import Safe


class Allocation(SubgraphEntry):
    def __init__(self, id: str, claimedAmount: str, allocatedAmount: str):
        self.address = id.lower() if id is not None else None
        self.claimed_amount = Balance(f"{claimedAmount} wei wxHOPR")
        self.allocated_amount = Balance(f"{allocatedAmount} wei wxHOPR")
        self.linked_safes: set[Safe] = set()

    @property
    def unclaimed_amount(self) -> Balance:
        return self.allocated_amount - self.claimed_amount

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)
