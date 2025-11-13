from ...components.balance import Balance
from .entry import SubgraphEntry


class Account(SubgraphEntry):
    """
    An Account represents a single entry in the subgraph.
    """

    def __init__(self, address: str, redeemed_value: str):
        """
        Create a new Account.
        :param address: The address of the node.
        :param redeemed_value: The value of redemeed tickets.
        """

        self.address = address.lower() if address is not None else None
        self.redeemed_value = Balance(f"{redeemed_value} wxHOPR")
