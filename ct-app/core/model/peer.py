import asyncio
from typing import Union

from core.components.baseclass import Base
from core.components.decorators import formalin
from core.components.lockedvar import LockedVar
from core.components.messagequeue import MessageQueue
from packaging.version import Version
from prometheus_client import Gauge

from .address import Address

PEER_SPLIT_STAKE = Gauge("peer_split_stake", "Splitted stake", ["peer_id"])
PEER_TF_STAKE = Gauge("peer_tf_stake", "Transformed stake", ["peer_id"])
PEER_SAFE_COUNT = Gauge("peer_safe_count", "Number of safes", ["peer_id"])
PEER_VERSION = Gauge("peer_version", "Peer version", ["peer_id", "version"])


class Peer(Base):
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
        self.channel_balance = None

        self.safe_address = None
        self.safe_balance = 0
        self.safe_allowance = 0

        self._safe_address_count = None

        self.message_count = LockedVar("message_count", 0, infer_type=False)
        self._eligible = False

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
        PEER_VERSION.labels(self.address.id, str(value)).set(1)

    @property
    def node_address(self) -> str:
        return self.address.address

    @property
    def safe_address_count(self) -> int:
        if self._safe_address_count is None:
            self.safe_address_count = 1

        return self._safe_address_count

    @safe_address_count.setter
    def safe_address_count(self, value: int):
        self._safe_address_count = value

        PEER_SAFE_COUNT.labels(self.address.id).set(value)

    @property
    def split_stake(self) -> float:
        if self.safe_balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.safe_address_count is None:
            raise ValueError("Safe address count not set")
        if self.message_count is None:
            return 0

        split_stake = float(self.safe_balance) / float(self.safe_address_count) + float(
            self.channel_balance
        )
        PEER_SPLIT_STAKE.labels(self.address.id).set(split_stake)

        return split_stake

    @property
    async def message_delay(self) -> float:
        count = await self.message_count.get()
        if count := count:
            return (365 * 24 * 60 * 60) / count
        else:
            return None

    def is_eligible(
        self,
        min_allowance: float,
        min_stake: float,
        ct_nodes: list[Address],
        nft_holders: list[str],
        nft_threshold: float,
    ) -> bool:
        conditions: list[bool] = []

        conditions.append(self.safe_allowance < min_allowance)
        conditions.append(self.address in ct_nodes)
        conditions.append(
            self.safe_address in nft_holders and self.split_stake < nft_threshold
        )
        conditions.append(self.split_stake < min_stake)

        return all(conditions)

    @formalin(None)
    async def relay_message(self):
        if delay := await self.message_delay:
            await MessageQueue().buffer.put(self.address.id)
            print(f"Next message for {self.address.id} in {delay} seconds.")
            await asyncio.sleep(delay)
        else:
            self.debug(f"No messages for {self.address.id}, sleeping for 5 seconds.")
            await asyncio.sleep(5)
            return

    def __repr__(self):
        return f"Peer(address: {self.address})"

    def __eq__(self, other):
        return self.address == other.address

    def __hash__(self):
        return hash(self.address)

    @property
    def print_prefix(self) -> str:
        return f"0x..{self.address.id[-5:]}"
