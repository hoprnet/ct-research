from ...components.balance import Balance
from .entry import RPCEntry


class Allocation(RPCEntry):
    def __init__(self, address: str, schedule: str, amount: Balance, claimed: Balance):
        self.address = address
        self.schedule = schedule
        self.amount = amount
        self.claimed = claimed
        self.linked_safes = set()

    @property
    def unclaimed_amount(self) -> Balance:
        return self.amount - self.claimed

    @property
    def num_linked_safes(self) -> int:
        return len(self.linked_safes)
