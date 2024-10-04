from .entry import SubgraphEntry


class Safe(SubgraphEntry):
    """
    A Safe represents a single entry in the subgraph.
    """

    def __init__(self, address: str, balance: str, allowance: str, owners: list[str]):
        """
        Create a new Safe with the specified balance and allowance.
        :param balance: The balance of the safe.
        :param allowance: The allowance of the safe.
        """
        self.address = address
        self.balance = float(balance) if balance else 0
        self.allowance = float(allowance) if allowance else 0
        self.owners = owners
        self.additional_balance = 0

    @property
    def total_balance(self) -> float:
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

    @classmethod
    def default(cls):
        """
        Create a new Safe with default values.
        """
        return cls("", "0", "0", [])

    def __str__(self):
        return f"Safe({self.address}, {self.balance}, {self.additional_balance}, {self.allowance}, {self.owners})"
