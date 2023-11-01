import asyncio
from enum import Enum
from typing import Any

from tools import HoprdAPIHelper

from .address import Address
from .baseclass import Base
from .decorators import connectguard, flagguard
from .parameters import Parameters
from .peer import Peer


class LockedVar(Base):
    def __init__(self, name: str, value: Any, infer_type: bool = True):
        self.name = name
        self.value = value
        self.lock = asyncio.Lock()

        if infer_type:
            self.type = type(value)
        else:
            self.type = None

    async def get(self) -> Any:
        async with self.lock:
            if self.type:
                return self.type(self.value)
            return self.value

    async def set(self, value: Any):
        if self.type and not isinstance(value, self.type):
            self._warning(
                f"Trying to set value of type {type(value)} to {self.type}, ignoring"
            )

        async with self.lock:
            self.value = value

    @property
    def print_prefix(self):
        return f"LockedVar({self.name})"


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
    def __init__(self, url: str, key: str):
        self.api = HoprdAPIHelper(url, key)
        self.url = url
        self.address = None

        self.peers = LockedVar("peers", set[Peer]())
        self.outgoings = LockedVar("outgoings", [])
        self.incomings = LockedVar("incomings", [])
        self.connected = LockedVar("connected", False)

        self.params = Parameters()

    @property
    async def balance(self) -> dict:
        return await self.api.balances()

    async def healthcheck(self) -> dict:
        await self.retrieve_address()
        await self.connected.set(self.address is not None)

    @property
    def print_prefix(self):
        return f"{self.url}"

    async def retrieve_address(self):
        peer_id = await self.api.get_address("hopr")
        peer_address = await self.api.get_address("hopr")

        if not (peer_id and peer_address):
            self._warning("Could not retrieve peer_id or peer_address")
            self.address = None
        else:
            self.address = Address(peer_id, peer_address)

    @flagguard
    @connectguard
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        out_opens = (await self.outgoings.get()).filter(
            lambda c: ChannelStatus.is_open(c.status)
        )

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {p.address for p in await self.peers.get()}
        addresses_without_channels = all_addresses - addresses_with_channels

        for address in addresses_without_channels:
            await self.api.open_channel(address)

    @flagguard
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        in_opens = filter(
            lambda c: ChannelStatus.is_open(c.status), await self.incomings.get()
        )

        for channel in in_opens:
            await self.api.close_channel(channel.channel_id)

    @flagguard
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """

        out_pendings = filter(
            lambda c: ChannelStatus.is_pending(c.status), await self.outgoings.get()
        )

        for channel in out_pendings:
            await self.api.close_channel(channel.channel_id)

    @flagguard
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """

        out_opens = filter(
            lambda c: ChannelStatus.is_open(c.status), await self.outgoings.get()
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

    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
        peers = await self.api.peers(params=["peer_id", "peer_address"], quality=0.5)
        addresses = {Address(p["peer_id"], p["peer_address"]) for p in peers}

        await self.peers.set({Peer(address) for address in addresses})

    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)

        outgoings = filter(lambda c: c.source_peer_id == self.address.id, channels.all)

        await self.outgoings.set(list(outgoings))

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
