import asyncio
import random
from typing import Union

from packaging.version import Version
from prometheus_client import Gauge

from . import AsyncLoop, MessageFormat, MessageQueue
from .address import Address
from .decorators import flagguard, formalin, master

CHANNEL_STAKE = Gauge("ct_peer_channels_balance",
                      "Balance in outgoing channels", ["peer_id"])
DELAY = Gauge("ct_peer_delay", "Delay between two messages", ["peer_id"])
NODES_LINKED_TO_SAFE_COUNT = Gauge(
    "ct_peer_safe_count", "Number of nodes linked to the safes", ["peer_id", "safe"])
SECONDS_IN_A_NON_LEAP_YEAR = 365 * 24 * 60 * 60


class Peer:
    """
    Representation of a peer in the network. A peer is a node that is part of the network and not hosted by HOPR.
    """

    def __init__(self, id: str, address: str, version: str):
        """
        Create a new Peer with the specified id, address and version. The id refers to the peerId, the address refers to the native address of a node.
        :param id: The peer's peerId
        :param address: The peer's native address
        :param version: The reported peer's version
        """
        self.address = Address(id, address)
        self.version = version

        self.safe = None
        self._safe_address_count = None
        self._channel_balance = None

        self.yearly_message_count = 0

        self.params = None
        self.running = False

    def is_old(self, min_version: Union[str, Version]):
        """
        Check if the peer's version is older than the specified version.
        :param min_version: The minimum version to check against.
        """
        if isinstance(min_version, str):
            min_version = Version(min_version)

        return self.version < min_version

    @property
    def version(self) -> Version:
        return self._version

    @version.setter
    def version(self, value: Union[str, Version]):
        if not isinstance(value, Version):
            try:
                value = Version(value)
            except Exception:
                value = Version("0.0.0")

        self._version = value

    @property
    def channel_balance(self):
        return self._channel_balance

    @channel_balance.setter
    def channel_balance(self, value):
        self._channel_balance = value
        CHANNEL_STAKE.labels(self.address.hopr).set(
            value if value is not None else 0)

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
        NODES_LINKED_TO_SAFE_COUNT.labels(
            self.address.hopr, self.safe.address).set(value)

    @property
    def split_stake(self) -> float:
        if self.safe.balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.safe_address_count is None:
            raise ValueError("Safe address count not set")
        if self.yearly_message_count is None:
            return 0

        split_stake = float(self.safe.total_balance) / float(
            self.safe_address_count
        ) + float(self.channel_balance)

        return split_stake

    @property
    async def message_delay(self) -> float:
        value = None
        if self.yearly_message_count is not None and self.yearly_message_count > 0:
            value = SECONDS_IN_A_NON_LEAP_YEAR / self.yearly_message_count

        DELAY.labels(self.address.hopr).set(value if value is not None else 0)

        return value

    def is_eligible(
        self,
        min_allowance: float,
        min_stake: float,
        ct_nodes: list[Address],
        nft_holders: list[str],
        nft_threshold: float,
    ) -> bool:
        try:
            if self.safe.allowance < min_allowance:
                return False

            if self.address in ct_nodes:
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

    @master(flagguard, formalin)
    async def message_relay_request(self):
        if self.address is None:
            return

        if delay := await self.message_delay:
            message = MessageFormat(self.address.hopr)
            await MessageQueue().buffer.put(message)
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(
                random.normalvariate(
                    self.params.peer.sleep_mean_time,
                    self.params.peer.sleep_std_time
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
        return self.address == other.address

    def __hash__(self):
        return hash(self.address)
