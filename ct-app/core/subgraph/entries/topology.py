from typing import Optional

from .entry import SubgraphEntry


class Topology(SubgraphEntry):
    """
    Class that represents a single topology entry (from the API).
    """

    def __init__(self, address: Optional[str], channels_balance: int):
        """
        Create a new Topology with the specified address and channels_balance.
        :param address: The peer's native address.
        :param channels_balance: The peer's outgoing channels total balance.
        """
        self.address = address.lower() if address is not None else None
        self.channels_balance = channels_balance
