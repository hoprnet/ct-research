from core.rpc.entries.entry import RPCEntry


class Allocation(RPCEntry):
    def __init__(self, address: str, schedule: str, amount: str, claimed: str):
        self.address = address
        self.schedule = schedule
        self.amount = float(amount) / 1e18
        self.claimed = float(claimed) / 1e18
        self.linked_safes = set()

    @property
    def unclaimed_amount(self) -> float:
        return self.amount - self.claimed

    @property
    def num_linked_safes(self) -> int:
        return len(self.linked_safes)
