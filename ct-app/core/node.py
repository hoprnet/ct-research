# region Imports
import asyncio
from datetime import datetime

from prometheus_client import Gauge

from .components import (
    Base,
    HoprdAPI,
    LockedVar,
    MessageFormat,
    MessageQueue,
    Parameters,
    Utils,
)
from .components.decorators import connectguard, flagguard, formalin
from .model import Address, Peer
from .model.database import DatabaseConnection, RelayedMessages

# endregion

# region Metrics
BALANCE = Gauge("ct_balance", "Node balance", ["peer_id", "token"])
PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["peer_id"])
HEALTH = Gauge("ct_node_health", "Node health", ["peer_id"])
CHANNELS = Gauge("ct_channels", "Node channels", ["peer_id", "direction"])
CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels", ["peer_id"])
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
        self.message_distributed = dict[str, int]()

        self.running = False

    @property
    def log_prefix(self):
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

        address = Address(address["hopr"], address["native"])
        await self.address.set(address)

        return address

    @flagguard
    @formalin(None)
    async def healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        health = await self.api.healthyz()
        await self.connected.set(health)

        if addr := await self.retrieve_address():
            HEALTH.labels(addr.id).set(int(health))
            if not health:
                self.warning("Node is not reachable.")
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
                    CHANNELS_OPS.labels(addr.id, "opened").inc()
            else:
                self.warning(f"Failed to open channel to {address}")

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
                    CHANNELS_OPS.labels(addr.id, "incoming_closed").inc()
            else:
                self.warning(f"Failed to close channel {channel.channel_id}")

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
                    CHANNELS_OPS.labels(addr.id, "pending_closed").inc()
            else:
                self.warning(f"Failed to close pending channel {channel.channel_id}")

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
                    CHANNELS_OPS.labels(addr.id, "old_closed").inc()
            else:
                self.warning(f"Failed to close channel {channel_id}")

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
                        CHANNELS_OPS.labels(addr.id, "fund").inc()
                else:
                    self.warning(f"Failed to fund channel {channel.channel_id}")

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
            CHANNELS.labels(addr.id, "outgoing").set(len(outgoings))

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
            CHANNELS.labels(addr.id, "incoming").set(len(incomings))

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
        CHANNEL_FUNDS.labels(node_address.id).set(funds)

        return funds

    @flagguard
    @formalin("Checking inbox for messages, and maybe storing to db")
    @connectguard
    async def relayed_messages_to_db(self):
        """
        Check the inbox for messages.
        """
        address = await self.address.get()

        messages = []
        for m in await self.api.messages_pop_all():
            try:
                message = MessageFormat.parse(m.body)
            except ValueError as err:
                self.error(f"Error while parsing message: {err}")
                continue
            messages.append(message)

        for message in messages:
            relayer = message.relayer
            if relayer not in self.message_distributed:
                self.message_distributed[relayer] = 0
            self.message_distributed[relayer] += 1

        entries = []
        for peer, count in self.message_distributed.items():
            if count < self.params.storage.count:
                continue

            entries.append(
                RelayedMessages(
                    relayer=peer,
                    sender=address.id,
                    count=count,
                    timestamp=datetime.now(),
                )
            )

        self.info(f"Storing relayed messages entries for {len(entries)} peers")

        try:
            DatabaseConnection.session().add_all(entries)
            DatabaseConnection.session().commit()
        except Exception as err:
            self.error(f"Database error while storing relayed messages entries: {err}")
        else:
            for entry in entries:
                self.message_distributed[entry.relayer] -= entry.count

    @formalin(None)
    async def watch_message_queue(self):
        message: MessageFormat = await MessageQueue().buffer.get()
        sender = (await self.address.get()).id
        asyncio.create_task(
            self.api.send_message(sender, message.format(), [message.relayer])
        )

    async def tasks(self):
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
            self.relayed_messages_to_db,
        ]

        return callbacks

    def __str__(self):
        return f"Node(id='{self.url}')"

    def __repr__(self):
        return f"Node(id='{self.url}')"

    @classmethod
    def fromCredentials(cls, addresses: list[str], keys: list[str]):
        return [cls(address, key) for address, key in zip(addresses, keys)]
