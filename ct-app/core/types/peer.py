from typing import Optional

from prometheus_client import Gauge

from .address import Address
from .balance import Balance

CHANNEL_STAKE = Gauge("ct_peer_channels_balance", "Balance in outgoing channels", ["address"])
QUALIFYING_CHANNELS = Gauge(
    "ct_peer_qualifying_channels",
    "Open outgoing channels holding at least the minimum channel balance",
    ["address"],
)


class Peer:
    """
    Representation of a peer in the network. A peer is a node that is part of the network and not
    hosted by HOPR.
    """

    def __init__(self, address: str):
        """
        Create a new Peer with the specified address. The address refers to the native
        address of a node.
        :param address: The peer's native address
        """
        self.address = Address(address)

        self._channel_balance: Optional[Balance] = None
        self._qualifying_channels: int = 0

        # Whether this CT node currently sees the peer.
        self.reachable: bool = True

    @property
    def channel_balance(self) -> Optional[Balance]:
        return self._channel_balance

    @channel_balance.setter
    def channel_balance(self, value: Balance):
        self._channel_balance = value
        CHANNEL_STAKE.labels(self.address.native).set(
            float(value.value if value is not None else 0)
        )

    @property
    def qualifying_channels(self) -> int:
        return self._qualifying_channels

    @qualifying_channels.setter
    def qualifying_channels(self, value: int):
        self._qualifying_channels = value
        QUALIFYING_CHANNELS.labels(self.address.native).set(value)

    def __repr__(self):
        return f"Peer(address: {self.address})"

    def __eq__(self, other):
        if hasattr(other, "address"):
            return self.address == other.address
        else:
            return self.address == other

    def __hash__(self):
        return hash(self.address)
