import asyncio
from datetime import datetime
from typing import Union

from core.components import AsyncLoop, Base, LockedVar, MessageFormat, MessageQueue
from core.components.decorators import flagguard, formalin
from packaging.version import Version
from prometheus_client import Gauge

from .address import Address
from .database import DatabaseConnection, SentMessages

STAKE = Gauge("ct_peer_stake", "Stake", ["peer_id", "type"])
SAFE_COUNT = Gauge("ct_peer_safe_count", "Number of safes", ["peer_id"])
VERSION = Gauge("ct_peer_version", "Peer version", ["peer_id", "version"])
DELAY = Gauge("ct_peer_delay", "Delay between two messages", ["peer_id"])


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

        self.yearly_message_count = LockedVar(
            "yearly_message_count", 0, infer_type=False
        )

        self.last_db_storage = datetime.now()
        self.message_count = LockedVar("message_count", 0)

        self.params = None
        self.running = False

    @property
    def running(self) -> bool:
        return self._running

    @running.setter
    def running(self, value: bool):
        self._running = value
        if value is True:
            AsyncLoop.add(self.message_relay_request)
            AsyncLoop.add(self.sent_messages_to_db)

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
        VERSION.labels(self.address.id, str(value)).set(1)

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
        SAFE_COUNT.labels(self.address.id).set(value)

    @property
    def split_stake(self) -> float:
        if self.safe_balance is None:
            raise ValueError("Safe balance not set")
        if self.channel_balance is None:
            raise ValueError("Channel balance not set")
        if self.safe_address_count is None:
            raise ValueError("Safe address count not set")
        if self.yearly_message_count is None:
            return 0

        split_stake = float(self.safe_balance) / float(self.safe_address_count) + float(
            self.channel_balance
        )
        STAKE.labels(self.address.id, "split").set(split_stake)

        return split_stake

    @property
    async def message_delay(self) -> float:
        count = await self.yearly_message_count.get()

        value = None
        if count is not None and count > 0:
            value = (365 * 24 * 60 * 60) / count

        DELAY.labels(self.address.id).set(value if value is not None else 0)

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
            if self.safe_allowance < min_allowance:
                return False

            if self.address in ct_nodes:
                return False

            if (
                self.safe_address not in nft_holders
                and nft_threshold
                and self.split_stake < nft_threshold
            ):
                return False

            if self.split_stake < min_stake:
                return False
        except Exception:
            return False

        return True

    @flagguard
    @formalin(None)
    async def message_relay_request(self):
        if delay := await self.message_delay:
            message = MessageFormat(self.address.id, datetime.now())
            await MessageQueue().buffer.put(message)
            await self.message_count.inc(1)
            await asyncio.sleep(delay)
        else:
            self.debug(
                f"No messages for {self.address.id[-5:]}, sleeping for 60 seconds."
            )
            await asyncio.sleep(60)

    @flagguard
    @formalin(None)
    async def sent_messages_to_db(self):
        """
        Stores the distribution data in the database, if available.
        """
        now = datetime.now()
        count = await self.message_count.get()

        if (
            count < self.params.storage.count
            and (now - self.last_db_storage).total_seconds()
            < self.params.storage.timeout
        ):
            return

        self.info(
            f"Storing sent messages in the database for {self.address.id} (count: {count})"
        )
        entry = SentMessages(
            relayer=self.address.id,
            count=count,
            timestamp=now,
        )

        try:
            DatabaseConnection.session().add(entry)
            DatabaseConnection.session().commit()
        except Exception as err:
            self.error(f"Database error while storing sent messages entries: {err}")
        else:
            await self.message_count.sub(count)
            self.last_db_storage = now

    def __repr__(self):
        return f"Peer(address: {self.address})"

    def __eq__(self, other):
        return self.address == other.address

    def __hash__(self):
        return hash(self.address)

    @property
    def log_prefix(self) -> str:
        return f"peer ..{self.address.id[-5:]}"
