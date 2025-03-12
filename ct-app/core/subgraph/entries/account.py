from .entry import SubgraphEntry


class Account(SubgraphEntry):
    """
    An Account represents a single entry in the subgraph.
    """

    def __init__(self, address: str, redeemed_value: int):
        """
        Create a new Account.
        :param address: The address of the node.
        :param redeemed_value: The value of redemeed tickets.
        """

        self.address = address.lower() if address is not None else None
        self.redeemed_value = float(redeemed_value)

    @classmethod
    def fromSubgraphResult(cls, account: dict):
        """
        Create a new Account from the specified subgraph result.
        :param account: The subgraph result to create the Account from.
        """
        return cls(
            account["id"],
            account["redeemedValue"],
        )
