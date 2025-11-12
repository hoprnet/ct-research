import asyncio
import random
from typing import Optional

from prometheus_client import Gauge

from ..subgraph.entries.safe import Safe
from .address import Address
from .asyncloop import AsyncLoop
from .balance import Balance
from .config_parser.parameters import Parameters
from .decorators import keepalive
from .messages import MessageFormat, MessageQueue

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

        self.safe: Optional[Safe] = None
        self._safe_address_count: Optional[int] = None
        self._channel_balance: Optional[Balance] = None

        self.yearly_message_count: Optional[int] = 0

        self.params: Optional[Parameters] = None
        self.running: bool = False

    @property
    def channel_balance(self) -> Balance:
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
            self.safe_address_count = 1

        return self._safe_address_count

    @safe_address_count.setter
    def safe_address_count(self, value: int):
        self._safe_address_count = value
        NODES_LINKED_TO_SAFE_COUNT.labels(self.address.native, self.safe.address).set(value)

    @property
    def split_stake(self) -> Balance:
        if self.safe.balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.safe_address_count is None:
            raise ValueError("Safe address count not set")
        if self.yearly_message_count is None:
            return Balance.zero("wxHOPR")

        return self.safe.total_balance / self.safe_address_count + self.channel_balance

    @property
    def message_delay(self) -> Optional[float]:
        value = None
        if self.yearly_message_count is not None and self.yearly_message_count > 0:
            value = (
                SECONDS_IN_A_NON_LEAP_YEAR / self.yearly_message_count * 2
            )  # to account for the loopback session behavior

        DELAY.labels(self.address.native).set(value if value is not None else 0)

        return value

    def is_eligible(
        self,
        min_allowance: Balance,
        min_stake: Balance,
        nft_holders: list[str],
        nft_threshold: Balance,
        ct_nodes: list[str],
        exclusion_list: list[str],
    ) -> bool:
        try:
            if self.address.native in exclusion_list:
                return False

            if self.address.native in ct_nodes:
                return False

            if self.safe.allowance < min_allowance:
                return False

            if (
                self.safe.address not in nft_holders
                and nft_threshold
                and self.split_stake < nft_threshold
            ):
                return False

            if self.split_stake < min_stake:
                return False
        except Exception:
            return False

        return True

    @keepalive
    async def message_relay_request(self):
        if self.address is None:
            return

        if delay := self.message_delay:
            # minimum 3 as 2 of those packets will be sent as session initialization packets
            batch_size = self.params.peer.minimum_delay_between_batches / delay
            refactored_batch_size: int = max(3, int(batch_size + 0.5))

            message = MessageFormat(self.address.native, batch_size=refactored_batch_size)
            await MessageQueue().put(message)
            await asyncio.sleep(delay * batch_size)

        else:
            await asyncio.sleep(
                random.normalvariate(
                    self.params.peer.sleep_mean_time, self.params.peer.sleep_std_time
                )
            )

    def start_async_processes(self):
        if self.running is False:
            self.running = True
            AsyncLoop.add(self.message_relay_request)

    def stop_async_processes(self):
        self.running = False

    def __repr__(self):
        return f"Peer(address: {self.address}, safe: {self.safe})"

    def __eq__(self, other):
        if hasattr(other, "address"):
            return self.address == other.address
        else:
            return self.address == other

    def __hash__(self):
        return hash(self.address)
