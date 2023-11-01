import asyncio
from enum import Enum

from tools import HoprdAPIHelper, envvar

from .address import Address
from .baseclass import Base
from .decorators import connectguard, flagguard
from .parameters import Parameters
from .peer import Peer


class ChannelStatus(Enum):
    Open = "Open"
    PendingToClose = "PendingToClose"
    Closed = "Closed"

    @classmethod
    def is_pending(cls, value: str):
        return value == cls.PendingToClose.value

    @classmethod
    def is_open(cls, value: str):
        return value == cls.Open.value


class Node(Base):
    def __init__(self, address: str, key: str):
        self.api = HoprdAPIHelper(address, key)
        self.address = address
        self.peer_id = None

        self._peers = set[Peer]()
        self._outgoings = []
        self._incomings = []
        self._connected = False

        self.peers_lock = asyncio.Lock()
        self.outgoings_lock = asyncio.Lock()
        self.incomings_lock = asyncio.Lock()
        self.connected_lock = asyncio.Lock()

        self.params = Parameters()

    @property
    async def peers(self) -> set[Peer]:
        async with self.peers_lock:
            return self._peers

    async def set_peers(self, value: set[Peer]):
        async with self.peers_lock:
            self._peers = value

    @property
    async def outgoings(self) -> []:
        async with self.outgoings_lock:
            return self._outgoings

    async def set_outgoings(self, value: []):
        async with self.outgoings_lock:
            self._outgoings = value

    @property
    async def incomings(self) -> []:
        async with self.incomings_lock:
            return self._incomings

    async def set_incomings(self, value: []):
        async with self.incomings_lock:
            self._incomings = value

    @property
    async def balance(self) -> dict:
        return await self.api.balances()

    @property
    async def connected(self) -> bool:
        async with self.connected_lock:
            return self._connected

    async def set_connected(self, value: bool):
        async with self.connected_lock:
            self._connected = value

    async def healthcheck(self) -> dict:
        await self.retrieve_peer_id()
        await self.set_connected(self.peer_id is not None)

    @property
    def print_prefix(self):
        return f"{self.address}"

    async def retrieve_peer_id(self):
        self.peer_id = await self.api.get_address("hopr")

    @flagguard
    @connectguard
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        out_opens = [c for c in await self.outgoings if ChannelStatus.is_open(c.status)]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {p.address for p in await self.peers}
        addresses_without_channels = all_addresses - addresses_with_channels

        for address in addresses_without_channels:
            await self.api.open_channel(address)

    @flagguard
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        in_opens = [c for c in await self.incomings if ChannelStatus.is_open(c.status)]

        for channel in in_opens:
            await self.api.close_channel(channel.channel_id)

    @flagguard
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        out_pendings = [
            c for c in await self.outgoings if ChannelStatus.is_pending(c.status)
        ]

        for channel in out_pendings:
            await self.api.close_channel(channel.channel_id)

    @flagguard
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        out_opens = [c for c in await self.outgoings if ChannelStatus.is_open(c.status)]
        low_balances = [
            c
            for c in out_opens
            if int(c.balance) / 1e18 <= self.params.channel_min_balance
        ]

        for channel in low_balances:
            if channel.destination_peer_id in [p.id for p in await self.peers]:
                await self.api.fund_channel(
                    channel.channel_id, self.params.channel_funding_amount
                )

    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
        peers = await self.api.peers(params=["peer_id", "peer_address"], quality=0.5)
        addresses = {Address(p["peer_id"], p["peer_address"]) for p in peers}

        await self.set_peers([Peer(address) for address in addresses])

    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)

        outgoings = [c for c in channels.all if c.source_peer_id == self.peer_id]

        await self.set_outgoings(outgoings)

    @connectguard
    async def retrieve_incoming_channels(self):
        """
        Retrieve all incoming channels.
        """
        channels = await self.api.all_channels(False)

        incomings = [c for c in channels.all if c.destination_peer_id == self.peer_id]

        await self.set_incomings(incomings)

    def tasks(self):
        return [
            asyncio.create_task(self.healthcheck()),
            asyncio.create_task(self.retrieve_peers()),
            asyncio.create_task(self.retrieve_outgoing_channels()),
            asyncio.create_task(self.retrieve_incoming_channels()),
            asyncio.create_task(self.open_channels()),
            asyncio.create_task(self.close_incoming_channels()),
            asyncio.create_task(self.close_pending_channels()),
            asyncio.create_task(self.fund_channels()),
        ]

    def __str__(self):
        return f"Node(id='{self.peer_id}')"

    @classmethod
    def from_env(cls, address_var_name: str, key_var_name: str):
        address = envvar(address_var_name, str)
        key = envvar(key_var_name, str)

        return cls(address, key)
