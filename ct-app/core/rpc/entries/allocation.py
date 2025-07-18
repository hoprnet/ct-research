from core.components.balance import Balance
from core.rpc.entries.entry import RPCEntry


class Allocation(RPCEntry):
    def __init__(self, address: str, schedule: str, amount: Balance, claimed: Balance):
        self.address = address
        self.schedule = schedule
        self.amount = amount
        self.claimed = claimed
