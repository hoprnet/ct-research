from core.components.balance import Balance as UnitBalance

from .entry import SubgraphEntry
from .safe import Safe


class Balance(SubgraphEntry):
    """
    A Balance represents a single EOA balance in the subgraph.
    """

    def __init__(self, address: str, balance: str):
        """
        Create a new Balance with the specified balance.
        :param address: The address of the EOA.
        :param balance: The balance of the EOA.
        """
        self.address = address.lower() if address is not None else None
        self.balance = UnitBalance(f"{balance} wxHOPR")
        self.linked_safes: set[Safe] = set()

    @property
    def num_linked_safes(self):
        return len(self.linked_safes)
