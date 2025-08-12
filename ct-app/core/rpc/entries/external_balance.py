from core.components.balance import Balance
from core.rpc.entries.entry import RPCEntry


class ExternalBalance(RPCEntry):
    def __init__(self, address: str, amount: Balance):
        self.address = address
        self.amount = amount
        self.linked_safes = set()

    @property
    def num_linked_safes(self) -> int:
        return len(self.linked_safes)
