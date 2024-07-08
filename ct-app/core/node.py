# region Imports
from datetime import datetime

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.decorators import connectguard, flagguard, formalin
from .components.hoprd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.message_queue import MessageQueue
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.peer import Peer

# endregion

# region Metrics
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
# endregion


class Node(Base):
    """
    A Node represents a single node in the network, managed by HOPR, and used to distribute rewards.
    """

    def __init__(self, url: str, key: str):
        """
        Create a new Node with the specified url and key.
        :param url: The url of the node.
        :param key: The key of the node.
        """
        super().__init__()

        self.api: HoprdAPI = HoprdAPI(url, key)
        self.url = url

        self.address = LockedVar("address", None, infer_type=False)
        self.peers = LockedVar("peers", set[Peer]())
        self.outgoings = LockedVar("outgoings", [])
        self.incomings = LockedVar("incomings", [])
        self.connected = LockedVar("connected", False)

        self.peer_history = LockedVar("peer_history", dict[str, datetime]())

        self.params = Parameters()

        self.running = False

    @property
    def print_prefix(self):
        return self.url.split("//")[-1].split(".")[0]

    async def retrieve_address(self):
        """
        Retrieve the address of the node.
        """
        address = await self.api.get_address("all")

        if not isinstance(address, dict):
            return

        if "hopr" not in address or "native" not in address:
            return

        await self.address.set(Address(address["hopr"], address["native"]))

        return await self.address.get()

    @flagguard
    @formalin(None)
    async def healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        health = await self.api.healthyz()
        await self.connected.set(health)

        if addr := await self.retrieve_address():
            self.debug(f"Connection state: {health}")
            HEALTH.labels(addr.id).set(int(health))
        else:
            self.warning("No address found")

    @flagguard
    @formalin("Retrieving balances")
    @connectguard
    async def retrieve_balances(self):
        """
        Retrieve the balances of the node.
        """
        balances = await self.api.balances()
        node_address = await self.address.get()

        if balances is None:
            self.warning("Failed to retrieve balances")
            return

        if addr := node_address:
            for token, balance in balances.items():
                BALANCE.labels(addr.id, token).set(balance)

        return balances

    @flagguard
    @formalin("Opening channels")
    @connectguard
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        node_address = await self.address.get()

        out_opens = [c for c in await self.outgoings.get() if not c.status.isClosed]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {
            p.address.address
            for p in await self.peers.get()
            if not p.is_old(self.params.peer.minVersion)
        }
        addresses_without_channels = all_addresses - addresses_with_channels

        self.info(f"Addresses without channels: {len(addresses_without_channels)}")

        for address in addresses_without_channels:
            self.debug(f"Opening channel to {address}")
            ok = await self.api.open_channel(
                address,
                f"{int(self.params.channel.fundingAmount*1e18):d}",
            )
            if ok:
                self.info(f"Opened channel to {address}")
                if addr := node_address:
                    CHANNELS_OPENED.labels(addr.id).inc()
            else:
                self.warning(f"Failed to open channel to {address}")
            if addr := node_address:
                OPEN_CHANNELS_CALLS.labels(addr.id).inc()

        if addr := node_address:
            ADDRESSES_WOUT_CHANNELS.labels(addr.id).set(len(addresses_without_channels))

    @flagguard
    @formalin("Closing incoming channels")
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        node_address = await self.address.get()

        in_opens = [c for c in await self.incomings.get() if c.status.isOpen]

        for channel in in_opens:
            self.debug(f"Closing incoming channel {channel.channel_id}")
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.info(f"Closed channel {channel.channel_id}")
                if addr := node_address:
                    INCOMING_CHANNELS_CLOSED.labels(addr.id).inc()
            else:
                self.warning(f"Failed to close channel {channel.channel_id}")
            if addr := node_address:
                CLOSE_INCOMING_CHANNELS_CALLS.labels(addr.id).inc()

    @flagguard
    @formalin("Closing pending channels")
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        node_address = await self.address.get()
        outgoing_channels = await self.outgoings.get()
        out_pendings = [c for c in outgoing_channels if c.status.isPending]

        self.info(f"Pending channels: {len(out_pendings)}")

        for channel in out_pendings:
            self.debug(f"Closing pending channel {channel.channel_id}")
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.info(f"Closed pending channel {channel.channel_id}")
                if addr := node_address:
                    PENDING_CHANNELS_CLOSED.labels(addr.id).inc()
            else:
                self.warning(f"Failed to close pending channel {channel.channel_id}")
            if addr := node_address:
                CLOSE_PENDING_CHANNELS_CALLS.labels(addr.id).inc()

    @flagguard
    @formalin("Closing old channels")
    @connectguard
    async def close_old_channels(self):
        """
        Close channels that have been open for too long.
        """
        node_address = await self.address.get()

        outgoings = await self.outgoings.get()
        peer_history: dict[str, datetime] = await self.peer_history.get()
        to_peer_history = dict[str, datetime]()
        channels_to_close: list[str] = []

        address_to_channel_id = {
            c.destination_address: c.channel_id for c in outgoings if c.status.isOpen
        }

        for address, channel_id in address_to_channel_id.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (
                datetime.now() - timestamp
            ).total_seconds() < self.params.channel.maxAgeSeconds:
                continue

            channels_to_close.append(channel_id)

        await self.peer_history.update(to_peer_history)
        self.debug(f"Updated peer history with {len(to_peer_history)} new entries")

        self.info(f"Closing {len(channels_to_close)} old channels")
        for channel in channels_to_close:
            self.debug(f"Closing channel {channel}")
            ok = await self.api.close_channel(channel)

            if ok:
                self.info(f"Channel {channel} closed")
                if addr := node_address:
                    OLD_CHANNELS_CLOSED.labels(addr.id).inc()
            else:
                self.warning(f"Failed to close channel {channel_id}")

            if addr := node_address:
                CLOSE_OLD_CHANNELS_CALLS.labels(addr.id).inc()

    @flagguard
    @formalin("Funding channels")
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        node_address = await self.address.get()

        out_opens = [c for c in await self.outgoings.get() if c.status.isOpen]

        low_balances = [
            c
            for c in out_opens
            if int(c.balance) / 1e18 <= self.params.channel.minBalance
        ]

        self.info(f"Low balance channels: {len(low_balances)}")

        peer_ids = [p.address.id for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                self.debug(f"Funding channel {channel.channel_id}")
                ok = await self.api.fund_channel(
                    channel.channel_id, self.params.channel.fundingAmount * 1e18
                )
                if ok:
                    self.info(f"Funded channel {channel.channel_id}")
                    if addr := node_address:
                        FUNDED_CHANNELS.labels(addr.id).inc()
                else:
                    self.warning(f"Failed to fund channel {channel.channel_id}")
                if addr := node_address:
                    FUND_CHANNELS_CALLS.labels(addr.id).inc()

    @flagguard
    @formalin("Retrieving peers")
    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
        node_address = await self.address.get()

        results = await self.api.peers(
            params=["peer_id", "peer_address", "reported_version"], quality=0.5
        )

        peers = {
            Peer(item["peer_id"], item["peer_address"], item["reported_version"])
            for item in results
        }

        addresses_w_timestamp = {p.address.address: datetime.now() for p in peers}

        await self.peers.set(peers)
        await self.peer_history.update(addresses_w_timestamp)

        self.info(f"Peers: {len(peers)}")

        if addr := node_address:
            PEERS_COUNT.labels(addr.id).set(len(peers))

    @flagguard
    @formalin("Retrieving outgoing channels")
    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)
        node_address = await self.address.get()

        if not hasattr(channels, "all"):
            self.warning("No outgoing channels found")
            return

        if addr := node_address:
            outgoings = [
                c
                for c in channels.all
                if c.source_peer_id == addr.id and not c.status.isClosed
            ]

            await self.outgoings.set(outgoings)
            self.info(f"Outgoing channels: {len(outgoings)}")
            OUTGOING_CHANNELS.labels(addr.id).set(len(outgoings))

    @flagguard
    @formalin("Retrieving incoming channels")
    @connectguard
    async def retrieve_incoming_channels(self):
        """
        Retrieve all incoming channels.
        """
        channels = await self.api.all_channels(False)
        node_address = await self.address.get()

        if not hasattr(channels, "all"):
            self.warning("No incoming channels found")
            return

        if addr := node_address:
            incomings = [
                c
                for c in channels.all
                if c.destination_peer_id == addr.id and not c.status.isClosed
            ]

            await self.incomings.set(incomings)
            self.info(f"Incoming channels: {len(incomings)}")
            INCOMING_CHANNELS.labels(addr.id).set(len(incomings))

    @flagguard
    @formalin("Retrieving total funds")
    @connectguard
    async def get_total_channel_funds(self):
        """
        Retrieve total funds.
        """
        channels = await self.outgoings.get()
        node_address = await self.address.get()

        if node_address is None:
            return

        results = await Utils.balanceInChannels(channels)

        if node_address.id not in results:
            self.warning("Funding info not found")
            return

        funds = results[node_address.id].get("channels_balance", 0)

        self.info(f"Channels funds: {funds}")
        TOTAL_CHANNEL_FUNDS.labels(node_address.id).set(funds)

        return funds

    @formalin(None)
    async def consume(self):
        relayer = await MessageQueue().buffer.get()
        sender = (await self.address.get()).id
        print(f"Should send a message through {relayer} back to {sender}")
        # TODO: replace with await self.api.send_message(sender, "This is CT", [relayer])

    async def tasks(self):
        self.info("Starting node")

        callbacks = [
            self.healthcheck,
            self.retrieve_peers,
            self.retrieve_outgoing_channels,
            self.retrieve_incoming_channels,
            self.retrieve_balances,
            self.open_channels,
            self.fund_channels,
            self.close_old_channels,
            self.close_incoming_channels,
            self.close_pending_channels,
            self.get_total_channel_funds,
        ]

        return callbacks

    def __str__(self):
        return f"Node(id='{self.url}')"

    @classmethod
    def fromCredentials(cls, addresses: list[str], keys: list[str]):
        return [cls(address, key) for address, key in zip(addresses, keys)]
