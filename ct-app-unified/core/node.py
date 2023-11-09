import asyncio

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.channelstatus import ChannelStatus
from .components.decorators import connectguard, flagguard, formalin
from .components.horpd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .model.address import Address
from .model.peer import Peer

BALANCE = Gauge("balance", "Node balance", ["peer_id", "token"])
PEERS_COUNT = Gauge("peers_count", "Node peers", ["peer_id"])
HEALTH = Gauge("node_health", "Node health", ["peer_id"])
CHANNELS_OPENED = Gauge("channels_opened", "Node channels opened", ["peer_id"])
INCOMING_CHANNELS_CLOSED = Gauge(
    "incoming_channels_closed", "Node's incoming channels closed", ["peer_id"]
)
PENDING_CHANNELS_CLOSED = Gauge(
    "pending_channels_closed", "Node's pending channels closed", ["peer_id"]
)
OUTGOING_CHANNELS = Gauge("outgoing_channels", "Node's outgoing channels", ["peer_id"])
INCOMING_CHANNELS = Gauge("incoming_channels", "Node's incoming channels", ["peer_id"])


class Node(Base):
    flag_prefix = "NODE_"

    def __init__(self, url: str, key: str):
        super().__init__()

        self.api: HoprdAPI = HoprdAPI(url, key)
        self.url = url
        self.address = None

        self.peers = LockedVar("peers", set[Peer]())
        self.outgoings = LockedVar("outgoings", [])
        self.incomings = LockedVar("incomings", [])
        self.connected = LockedVar("connected", False)

        self.params = Parameters()

        self.started = False

    @property
    async def balance(self) -> dict:
        return await self.api.balances()

    @property
    def print_prefix(self):
        return f"{self.url}"

    async def _retrieve_address(self):
        addresses = await self.api.get_address("all")
        self.address = Address(addresses["hopr"], addresses["native"])

    @flagguard
    @formalin(None)
    async def healthcheck(self) -> dict:
        await self._retrieve_address()
        await self.connected.set(self.address is not None)

        self._debug(f"Connection state: {await self.connected.get()}")
        HEALTH.labels(self.address.id).set(int(await self.connected.get()))

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
        out_opens = filter(
            lambda c: ChannelStatus.isOpen(c.status), await self.outgoings.get()
        )

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {p.address for p in await self.peers.get()}
        addresses_without_channels = all_addresses - addresses_with_channels

        for address in addresses_without_channels:
            await self.api.open_channel(address, self.param.channel_funding_amount)

        CHANNELS_OPENED.labels(self.address.id).set(len(addresses_without_channels))

    @flagguard
    @formalin("Closing incoming channels")
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        in_opens = filter(
            lambda c: ChannelStatus.isOpen(c.status), await self.incomings.get()
        )

        for channel in in_opens:
            await self.api.close_channel(channel.channel_id)

        INCOMING_CHANNELS_CLOSED.labels(self.address.id).set(len(in_opens))

    @flagguard
    @formalin("Closing pending channels")
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """

        out_pendings = filter(
            lambda c: ChannelStatus.isPending(c.status), await self.outgoings.get()
        )

        for channel in out_pendings:
            await self.api.close_channel(channel.channel_id)

        PENDING_CHANNELS_CLOSED.labels(self.address.id).set(len(out_pendings))

    @flagguard
    @formalin("Funding channels")
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """

        out_opens = filter(
            lambda c: ChannelStatus.isOpen(c.status), await self.outgoings.get()
        )
        low_balances = filter(
            lambda c: int(c.balance) <= self.params.channel_min_balance, out_opens
        )

        peer_ids = [p.id for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                await self.api.fund_channel(
                    channel.channel_id, self.params.channel_funding_amount
                )

    @flagguard
    @formalin("Retrieving peers")
    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """

        results = await self.api.peers(params=["peer_id", "peer_address"], quality=0.5)
        peers = {Peer(item["peer_id"], item["peer_address"]) for item in results}

        await self.peers.set(peers)
        PEERS_COUNT.labels(self.address.id).set(len(peers))

    @flagguard
    @formalin("Retrieving outgoing channels")
    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)

        outgoings = filter(lambda c: c.source_peer_id == self.address.id, channels.all)

        await self.outgoings.set(list(outgoings))
        OUTGOING_CHANNELS.labels(self.address.id).set(len(list(outgoings)))

    @flagguard
    @formalin("Retrieving incoming channels")
    @connectguard
    async def retrieve_incoming_channels(self):
        """
        Retrieve all incoming channels.
        """
        channels = await self.api.all_channels(False)

        incomings = filter(
            lambda c: c.destination_peer_id == self.address.id, channels.all
        )

        await self.incomings.set(list(incomings))
        INCOMING_CHANNELS.labels(self.address.id).set(len(list(incomings)))

    def tasks(self):
        self._info("Starting node")
        return [
            asyncio.create_task(self.healthcheck()),
            asyncio.create_task(self.retrieve_peers()),
            asyncio.create_task(self.retrieve_outgoing_channels()),
            asyncio.create_task(self.retrieve_incoming_channels()),
            asyncio.create_task(self.retrieve_balances()),
            asyncio.create_task(self.open_channels()),
            asyncio.create_task(self.close_incoming_channels()),
            asyncio.create_task(self.close_pending_channels()),
            asyncio.create_task(self.fund_channels()),
        ]

    def __str__(self):
        return f"Node(id='{self.peer_id}')"

    @classmethod
    def fromAddressListAndKey(cls, addresses: list[str], key: str):
        return [cls(address, key) for address in addresses]
