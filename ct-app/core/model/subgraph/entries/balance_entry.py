from .entry import SubgraphEntry
from .safe_entry import SafeEntry


class BalanceEntry(SubgraphEntry):
    """
    A BalanceEntry represents a single EOA balance in the subgraph.
    """

    def __init__(self, address: str, balance: str):
        """
        Create a new BalanceEntry with the specified balance.
        :param balance: The balance of the safe.
        :param allowance: The allowance of the safe.
        """
        self.address = address
        self.balance = float(balance) if balance else 0
        self.linked_safes: set[SafeEntry] = set()

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)

    def __str__(self):
        return f"BalanceEntry({self.address}, {self.balance})"
