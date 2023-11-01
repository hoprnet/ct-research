import asyncio
from enum import Enum

from tools import HoprdAPIHelper, envvar

from . import utils as utils
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


class Node:
    def __init__(self, address: str, key: str):
        self.api = HoprdAPIHelper(address, key)
        self.address = address
        self.peer_id = utils.random_string(5)

        self._peers = set[Peer]()
        self._outgoings = []

        self.peers_lock = asyncio.Lock()
        self.outgoings_lock = asyncio.Lock()

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
    async def balance(self) -> dict:
        return await self.api.balances()

    async def retrieve_peers(self):
        """
        TODO: retrieve real peers from the network.
        """
        peers = [Peer.random() for _ in range(3)]
        await self.set_peers(peers)

    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        out_opens = [c for c in self.outgoings if ChannelStatus.is_open(c.status)]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {p.address for p in await self.peers}
        addresses_without_channels = all_addresses - addresses_with_channels

        for address in addresses_without_channels:
            await self.api.open_channel(address)

    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        out_pendings = [c for c in self.outgoings if ChannelStatus.is_pending(c.status)]

        for channel in out_pendings:
            await self.api.close_channel(channel.channel_id)

    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        out_opens = [c for c in self.outgoings if ChannelStatus.is_open(c.status)]
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

    async def retrieve_outgoing_channels(self):
        """
        Retrieve all channels.
        """
        channels = await self.api.all_channels()

        outgoings = [c for c in channels.all if c.source_peer_id == self.peer_id]

        await self.set_outgoings(outgoings)

    def __str__(self):
        return f"Node(id='{self.peer_id}')"

    @classmethod
    def from_env(cls, address_var_name: str, key_var_name: str):
        address = envvar(address_var_name, str)
        key = envvar(key_var_name, str)

        return cls(address, key)
