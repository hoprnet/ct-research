import asyncio
import random
from datetime import datetime

from packaging.version import Version
from prometheus_client import Gauge

from core.components import AsyncLoop, Base, MessageFormat, MessageQueue
from core.components.decorators import flagguard, formalin

from .address import Address
from .database import DatabaseConnection, SentMessages

STAKE = Gauge("ct_peer_stake", "Stake", ["peer_id", "type"])
SAFE_COUNT = Gauge("ct_peer_safe_count", "Number of safes", ["peer_id"])
DELAY = Gauge("ct_peer_delay", "Delay between two messages", ["peer_id"])

SECONDS_IN_A_NON_LEAP_YEAR = 365 * 24 * 60 * 60


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

        self.safe = None
        self._safe_address_count = None

        self.yearly_message_count = 0

        self.last_db_storage = datetime.now()
        self.message_count = 0

        self.params = None
        self.running = False

    def is_old(self, min_version: str | Version):
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
    def version(self, value: str | Version):
        if not isinstance(value, Version):
            try:
                value = Version(value)
            except Exception:
                value = Version("0.0.0")

        self._version = value

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
        STAKE.labels(self.address.id, "split").set(split_stake)

        return split_stake

    @property
    async def message_delay(self) -> float:
        value = None
        if self.yearly_message_count is not None and self.yearly_message_count > 0:
            value = SECONDS_IN_A_NON_LEAP_YEAR / self.yearly_message_count

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

    @flagguard
    @formalin
    async def message_relay_request(self):
        if self.address is None:
            return

        if delay := await self.message_delay:
            message = MessageFormat(self.address.id, datetime.now())
            await MessageQueue().buffer.put(message)
            self.message_count += 1
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(
                random.normalvariate(
                    self.params.peer.initialSleep.mean,
                    self.params.peer.initialSleep.std,
                )
            )

    @flagguard
    @formalin
    async def sent_messages_to_db(self):
        """
        Stores the distribution data in the database, if available.
        """
        now = datetime.now()
        count = self.message_count

        if (
            count < self.params.storage.count
            and (now - self.last_db_storage).total_seconds()
            < self.params.storage.timeout
        ):
            return

        entry = SentMessages(
            relayer=self.address.id,
            count=count,
            timestamp=now,
        )

        try:
            DatabaseConnection.session().add(entry)
            DatabaseConnection.session().commit()
        except Exception as err:
            self.error(
                f"Database error while storing sent messages entries: {err}")
        else:
            self.message_count -= count
            self.last_db_storage = now

    def start_async_processes(self):
        if self.running is False:
            self.running = True
            AsyncLoop.add(self.message_relay_request)
            AsyncLoop.add(self.sent_messages_to_db)

    def stop_async_processes(self):
        self.running = False

    def __repr__(self):
        return f"Peer(address: {self.address}, safe: {self.safe})"

    def __eq__(self, other):
        return self.address == other.address

    def __hash__(self):
        return hash(self.address)

    @property
    def log_prefix(self) -> str:
        return f"peer ..{self.address.id[-5:]}"
