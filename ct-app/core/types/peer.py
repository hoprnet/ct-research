import random
from typing import Optional

from prometheus_client import Gauge

from .address import Address
from .balance import Balance
from .message_format import MessageFormat

CHANNEL_STAKE = Gauge("ct_peer_channels_balance", "Balance in outgoing channels", ["address"])
DELAY = Gauge("ct_peer_delay", "Delay between two messages", ["address"])
NODES_LINKED_TO_SAFE_COUNT = Gauge(
    "ct_peer_safe_count", "Number of nodes linked to the safes", ["address", "safe"]
)
SECONDS_IN_A_NON_LEAP_YEAR = 365 * 24 * 60 * 60


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

        self.safe_address: Optional[str] = None
        self.safe_balance: Optional[Balance] = None
        self._safe_address_count: Optional[int] = None
        self._channel_balance: Optional[Balance] = None
        self._allocated_balance: Optional[Balance] = None
        self.redeemed_amount: Optional[Balance] = None

        self.yearly_message_count: Optional[float] = 0

        self.running: bool = False

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
    def node_address(self) -> str:
        return self.address.native

    @property
    def safe_address_count(self) -> int:
        if self._safe_address_count is None:
            self._safe_address_count = 1

        return self._safe_address_count

    @safe_address_count.setter
    def safe_address_count(self, value: int):
        self._safe_address_count = value
        if self.safe_address:
            NODES_LINKED_TO_SAFE_COUNT.labels(self.address.native, self.safe_address).set(value)

    @property
    def allocated_balance(self) -> Optional[Balance]:
        return self._allocated_balance

    def set_allocation(
        self, safe_address: Optional[str], safe_balance: Optional[Balance], count: int
    ):
        self.safe_address = safe_address
        self.safe_balance = safe_balance

        if safe_address is None:
            self._allocated_balance = None
            self._safe_address_count = None
            return

        self._safe_address_count = max(1, count)
        if safe_balance is None:
            self._allocated_balance = None
            return

        self._allocated_balance = safe_balance / self._safe_address_count

    @property
    def effective_stake(self) -> Balance:
        if self.allocated_balance is not None:
            return self.allocated_balance

        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.yearly_message_count is None:
            return Balance.zero("wxHOPR")

        return self.channel_balance

    @property
    def split_stake(self) -> Balance:
        return self.effective_stake

    @property
    def message_delay(self) -> Optional[float]:
        value = self._message_delay_from_count()
        DELAY.labels(self.address.native).set(value if value is not None else 0)
        return value

    def _message_delay_from_count(self) -> Optional[float]:
        if self.yearly_message_count is None or self.yearly_message_count <= 0:
            return None
        return SECONDS_IN_A_NON_LEAP_YEAR / self.yearly_message_count * 2

    def relay_batch_size(self, delay: float, minimum_delay_between_batches: float) -> int:
        batch_size = minimum_delay_between_batches / delay
        return max(3, int(batch_size + 0.5))

    def build_relay_request(
        self, delay: float, minimum_delay_between_batches: float
    ) -> MessageFormat:
        batch_size = self.relay_batch_size(delay, minimum_delay_between_batches)
        return MessageFormat(self.address.native, batch_size=batch_size)

    def next_idle_sleep(self, sleep_mean_time: float, sleep_std_time: float) -> float:
        return random.normalvariate(sleep_mean_time, sleep_std_time)

    def is_eligible(
        self,
        min_stake: Balance,
        ct_nodes: list[str],
        exclusion_list: list[str],
    ) -> bool:
        if self.safe_address is None:
            return False

        if self.address.native in exclusion_list:
            return False

        if self.address.native in ct_nodes:
            return False

        try:
            if self.effective_stake < min_stake:
                return False
        except ValueError:
            return False

        return True

    def __repr__(self):
        return f"Peer(address: {self.address}, safe_address: {self.safe_address})"

    def __eq__(self, other):
        if hasattr(other, "address"):
            return self.address == other.address
        else:
            return self.address == other

    def __hash__(self):
        return hash(self.address)
