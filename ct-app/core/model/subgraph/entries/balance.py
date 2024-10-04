from .entry import SubgraphEntry
from .safe import Safe


class Balance(SubgraphEntry):
    """
    A Balance represents a single EOA balance in the subgraph.
    """

    def __init__(self, address: str, balance: str):
        """
        Create a new Balance with the specified balance.
        :param balance: The balance of the safe.
        :param allowance: The allowance of the safe.
        """
        self.address = address
        self.balance = float(balance) if balance else 0
        self.linked_safes: set[Safe] = set()

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)
