import asyncio
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.channelstatus import ChannelStatus
from .components.decorators import connectguard, flagguard, formalin
from .components.hoprd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.peer import Peer
from .model.topology_entry import TopologyEntry

BALANCE = Gauge("balance", "Node balance", ["peer_id", "token"])
PEERS_COUNT = Gauge("peers_count", "Node peers", ["peer_id"])
HEALTH = Gauge("node_health", "Node health", ["peer_id"])

OUTGOING_CHANNELS = Gauge("outgoing_channels", "Node's outgoing channels", ["peer_id"])
INCOMING_CHANNELS = Gauge("incoming_channels", "Node's incoming channels", ["peer_id"])

CHANNELS_OPENED = Gauge("channels_opened", "Node channels opened", ["peer_id"])
INCOMING_CHANNELS_CLOSED = Gauge(
    "incoming_channels_closed", "Node's incoming channels closed", ["peer_id"]
)
PENDING_CHANNELS_CLOSED = Gauge(
    "pending_channels_closed", "Node's pending channels closed", ["peer_id"]
)
OLD_CHANNELS_CLOSED = Gauge("old_channels_closed", "Old channels closed", ["peer_id"])

OPEN_CHANNELS_CALLS = Gauge(
    "open_channels_calls", "Calls to open channels", ["peer_id"]
)
CLOSE_INCOMING_CHANNELS_CALLS = Gauge(
    "close_incoming_channels_calls", "Calls to close incoming channels", ["peer_id"]
)
CLOSE_PENDING_CHANNELS_CALLS = Gauge(
    "close_pending_channels_calls", "Calls to close pending channels", ["peer_id"]
)

CLOSE_OLD_CHANNELS_CALLS = Gauge(
    "close_old_channels_calls", "Calls to close old channels", ["peer_id"]
)

FUNDED_CHANNELS = Gauge("funded_channels", "Funded channels", ["peer_id"])
FUND_CHANNELS_CALLS = Gauge(
    "fund_channels_calls", "Calls to fund channels", ["peer_id"]
)
ADDRESSES_WOUT_CHANNELS = Gauge(
    "addresses_wout_channels", "Addresses without channels", ["peer_id"]
)
TOTAL_CHANNEL_FUNDS = Gauge(
    "total_channel_funds", "Total funds in outgoing channels", ["peer_id"]
)


class Node(Base):
    flag_prefix = "NODE_"

    def __init__(self, url: str, key: str):
        super().__init__()

        self.api: HoprdAPI = HoprdAPI(url, key)
        self.url = url
        self.address: Optional[Address] = None

        self.peers = LockedVar("peers", set[Peer]())
        self.outgoings = LockedVar("outgoings", [])
        self.incomings = LockedVar("incomings", [])
        self.connected = LockedVar("connected", False)

        self.peer_history = LockedVar("peer_history", dict[str, datetime]())

        self.params = Parameters()

        self.started = False

    @property
    async def balance(self) -> dict[str, int]:
        return await self.api.balances()

    @property
    def print_prefix(self):
        return f"{self.url}"

    async def _retrieve_address(self):
        address = await self.api.get_address("all")

        if not isinstance(address, dict):
            return

        if "hopr" not in address or "native" not in address:
            return

        self.address = Address(address["hopr"], address["native"])

    @flagguard
    @formalin(None)
    async def healthcheck(self):
        await self._retrieve_address()
        await self.connected.set(self.address is not None)

        if address := self.address:
            self.debug(f"Connection state: {await self.connected.get()}")
            HEALTH.labels(address.id).set(int(await self.connected.get()))

    @flagguard
    @formalin("Retrieving balances")
    @connectguard
    async def retrieve_balances(self):
        for token, balance in (await self.balance).items():
            BALANCE.labels(self.address.id, token).set(balance)

    @flagguard
    @formalin("Opening channels")
    @connectguard
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        out_opens = [
            c
            for c in await self.outgoings.get()
            if not ChannelStatus.isClosed(c.status)
        ]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {p.address.address for p in await self.peers.get()}
        addresses_without_channels = all_addresses - addresses_with_channels

        self.debug(f"Addresses without channels: {len(addresses_without_channels)}")

        for address in addresses_without_channels:
            ok = await self.api.open_channel(
                address,
                f"{int(self.params.channel.funding_amount*1e18):d}",
            )
            if ok:
                self.debug(f"Opened channel to {address}")
                CHANNELS_OPENED.labels(self.address.id).inc()
            OPEN_CHANNELS_CALLS.labels(self.address.id).inc()

        ADDRESSES_WOUT_CHANNELS.labels(self.address.id).set(
            len(addresses_without_channels)
        )

    @flagguard
    @formalin("Closing incoming channels")
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """

        in_opens = [
            c for c in await self.incomings.get() if ChannelStatus.isOpen(c.status)
        ]

        for channel in in_opens:
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.debug(f"Closed channel {channel.channel_id}")
                INCOMING_CHANNELS_CLOSED.labels(self.address.id).inc()
            CLOSE_INCOMING_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Closing pending channels")
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """

        out_pendings = [
            c for c in await self.outgoings.get() if ChannelStatus.isPending(c.status)
        ]

        self.debug(f"Pending channels: {len(out_pendings)}")

        for channel in out_pendings:
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.debug(f"Closed pending channel {channel.channel_id}")
                PENDING_CHANNELS_CLOSED.labels(self.address.id).inc()
            CLOSE_PENDING_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Closing old channels")
    @connectguard
    async def close_old_channels(self):
        """
        Close channels that have been open for too long.
        """
        outgoings = await self.outgoings.get()
        peer_history: dict[str, datetime] = await self.peer_history.get()
        to_peer_history = dict[str, datetime]()
        channels_to_close: list[str] = []

        address_to_channel_id = {
            c.destination_address: c.channel_id
            for c in outgoings
            if ChannelStatus.isOpen(c.status)
        }

        for address, channel_id in address_to_channel_id.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (
                datetime.now() - timestamp
            ).total_seconds() < self.params.channel.max_age_seconds:
                continue

            channels_to_close.append(channel_id)

        await self.peer_history.update(to_peer_history)
        self.debug(f"Updated peer history with {len(to_peer_history)} new entries")

        self.info(f"Closing {len(channels_to_close)} old channels")
        for channel in channels_to_close:
            ok = await self.api.close_channel(channel)

            if ok:
                self.debug(f"Channel {channel} closed")
                OLD_CHANNELS_CLOSED.labels(self.address.id).inc()
            else:
                self.debug(f"Failed to close channel {channel_id}")

            CLOSE_OLD_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Funding channels")
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """

        out_opens = [
            c for c in await self.outgoings.get() if ChannelStatus.isOpen(c.status)
        ]

        low_balances = [
            c for c in out_opens if int(c.balance) <= self.params.channel.min_balance
        ]

        self.debug(f"Low balance channels: {len(low_balances)}")

        peer_ids = [p.address.id for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                ok = await self.api.fund_channel(
                    channel.channel_id, self.params.channel.funding_amount
                )
                if ok:
                    self.debug(f"Funded channel {channel.channel_id}")
                    FUNDED_CHANNELS.labels(self.address.id).inc()
                FUND_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Retrieving peers")
    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """

        results = await self.api.peers(params=["peer_id", "peer_address"], quality=0.5)
        peers = {Peer(item["peer_id"], item["peer_address"]) for item in results}

        addresses_w_timestamp = {p.address.address: datetime.now() for p in peers}

        await self.peers.set(peers)
        await self.peer_history.update(addresses_w_timestamp)

        self.debug(f"Peers: {len(peers)}")
        PEERS_COUNT.labels(self.address.id).set(len(peers))

    @flagguard
    @formalin("Retrieving outgoing channels")
    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)

        outgoings = [
            c
            for c in channels.all
            if c.source_peer_id == self.address.id
            and not ChannelStatus.isClosed(c.status)
        ]

        await self.outgoings.set(outgoings)
        self.debug(f"Outgoing channels: {len(outgoings)}")
        OUTGOING_CHANNELS.labels(self.address.id).set(len(outgoings))

    @flagguard
    @formalin("Retrieving incoming channels")
    @connectguard
    async def retrieve_incoming_channels(self):
        """
        Retrieve all incoming channels.
        """
        channels = await self.api.all_channels(False)

        incomings = [
            c
            for c in channels.all
            if c.destination_peer_id == self.address.id
            and not ChannelStatus.isClosed(c.status)
        ]

        await self.incomings.set(incomings)
        self.debug(f"Incoming channels: {len(incomings)}")
        INCOMING_CHANNELS.labels(self.address.id).set(len(incomings))

    @flagguard
    @formalin("Retrieving total funds")
    @connectguard
    async def get_total_channel_funds(self):
        """
        Retrieve total funds.
        """
        channels = await self.outgoings.get()

        results = await Utils.aggregatePeerBalanceInChannels(channels)

        if self.address.id not in results:
            return

        entry = TopologyEntry.fromDict(self.address.id, results[self.address.id])

        self.debug(f"Channels funds: { entry.channels_balance}")
        TOTAL_CHANNEL_FUNDS.labels(self.address.id).set(entry.channels_balance)

    def tasks(self):
        self.info("Starting node")
        return [
            asyncio.create_task(self.healthcheck()),
            asyncio.create_task(self.retrieve_peers()),
            asyncio.create_task(self.retrieve_outgoing_channels()),
            asyncio.create_task(self.retrieve_incoming_channels()),
            asyncio.create_task(self.retrieve_balances()),
            asyncio.create_task(self.open_channels()),
            asyncio.create_task(self.close_incoming_channels()),
            asyncio.create_task(self.close_pending_channels()),
            asyncio.create_task(self.close_old_channels()),
            asyncio.create_task(self.fund_channels()),
            asyncio.create_task(self.get_total_channel_funds()),
        ]

    def __str__(self):
        return f"Node(id='{self.url}')"

    @classmethod
    def fromAddressListAndKey(cls, addresses: list[str], key: str):
        return [cls(address, key) for address in addresses]