from core.rpc.entries.entry import RPCEntry


class ExternalBalance(RPCEntry):
    def __init__(self, address: str, amount: str):
        self.address = address
        self.amount = float(amount) / 1e18
        self.linked_safes = set()

    @property
    def num_linked_safes(self) -> int:
        return len(self.linked_safes)
