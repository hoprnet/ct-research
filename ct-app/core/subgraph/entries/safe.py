import random
from typing import Optional

from ...components.balance import Balance
from .entry import SubgraphEntry


class Safe(SubgraphEntry):
    """
    A Safe represents a single entry in the subgraph.
    """

    def __init__(self, address: str, balance: Optional[str], allowance: str, owners: list[str]):
        """
        Create a new Safe with the specified balance and allowance.
        :param balance: The balance of the safe.
        :param allowance: The allowance of the safe.
        """
        self.address = address.lower() if address is not None else None
        self.balance = (
            Balance(f"{balance} wxHOPR") if balance is not None else Balance.zero("wxHOPR")
        )
        self.allowance = (
            Balance(f"{allowance} wxHOPR") if allowance is not None else Balance.zero("wxHOPR")
        )
        self.owners = [owner.lower() for owner in owners if owner is not None]
        self.additional_balance = Balance.zero("wxHOPR")

    @property
    def total_balance(self) -> Balance:
        """
        Get the total balance of the safe.
        """
        return self.balance + self.additional_balance

    @classmethod
    def fromSubgraphResult(cls, safe: dict):
        """
        Create a new Safe from the specified subgraph result.
        :param safe: The subgraph result to create the Safe from.
        """
        return cls(
            safe["id"],
            safe["balance"]["wxHoprBalance"],
            safe["allowance"]["wxHoprAllowance"],
            [owner["owner"]["id"] for owner in safe["owners"]],
        )
