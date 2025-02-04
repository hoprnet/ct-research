from .entry import SubgraphEntry
from .to_channel import ToChannel


class Account(SubgraphEntry):
    """
    An Account represents a single entry in the subgraph.
    """

    def __init__(self, address: str, redeemed_value: int, channels: list[ToChannel]):
        """
        Create a new Account.
        :param address: The address of the node.
        :param redeemed_value: The value of redemeed tickets.
        :param channels: The channels of the node.
        """

        self.address = self.checksum(address)
        self.redeemed_value = float(redeemed_value)
        self.channels = channels


    @classmethod
    def fromSubgraphResult(cls, account: dict):
        """
        Create a new Account from the specified subgraph result.
        :param account: The subgraph result to create the Account from.
        """
        return cls(
            account["id"],
            account["redeemedValue"],
            [ToChannel.fromSubgraphResult(c) for c in account["toChannels"]],
        )
