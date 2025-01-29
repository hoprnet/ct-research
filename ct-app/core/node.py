# region Imports
from datetime import datetime

from prometheus_client import Gauge

from core.components.address import Address
from core.components.asyncloop import AsyncLoop

from .api import HoprdAPI, Protocol
from .baseclass import Base
from .components import LockedVar, Parameters, Peer, Utils
from .components.decorators import connectguard, flagguard, formalin, master
from .components.messages import MessageFormat, MessageQueue
from .components.node_helper import NodeHelper
from .components.session_to_socket import SessionToSocket

# endregion

# region Metrics
BALANCE = Gauge("ct_balance", "Node balance", ["peer_id", "token"])
CHANNELS = Gauge("ct_channels", "Node channels", ["peer_id", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds",
                      "Total funds in out. channels", ["peer_id"])
HEALTH = Gauge("ct_node_health", "Node health", ["peer_id"])
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "sender", "relayer"])
PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["peer_id"])
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

        self.peers = LockedVar("peers", set[Peer]())
        self.peer_history = LockedVar("peer_history", dict[str, datetime]())

        self.address = None
        self.channels = None
        self._safe_address = None

        self.params = Parameters()
        self.session_management = dict[str, SessionToSocket]()

        self.connected = False
        self.running = True

    @property
    async def safe_address(self):
        if self._safe_address is None:
            if info := await self.api.node_info():
                self._safe_address = info.hopr_node_safe

        return self._safe_address

    @property
    def log_prefix(self):
        return self.url.split("//")[-1].split(".")[0]

    async def retrieve_address(self):
        """
        Retrieve the address of the node.
        """
        addresses = await self.api.get_address()

        if addresses is None:
            return

        self.address = addresses
        return self.address

    async def _healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        health = await self.api.healthyz()
        self.connected = health

        if addr := await self.retrieve_address():
            HEALTH.labels(addr.hopr).set(int(health))
            if not health:
                self.warning("Node is not reachable.")
        else:
            self.warning("No address found")

    @master(flagguard, formalin)
    async def healthcheck(self):
        await self._healthcheck()

    @master(flagguard, formalin, connectguard)
    async def retrieve_balances(self):
        """
        Retrieve the balances of the node.
        """
        balances = await self.api.balances()

        if balances is None:
            return None
            
        if addr := self.address:
            for token, balance in vars(balances).items():
                if balance is None:
                    continue
                BALANCE.labels(addr.hopr, token).set(balance)

        return balances

    @master(flagguard, formalin, connectguard)
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        if self.channels is None:
            return

        out_opens = [
            c for c in self.channels.outgoing if not c.status.is_closed]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {
            p.address.native
            for p in await self.peers.get()
            if not p.is_old(self.params.peer.minVersion)
        }
        addresses_without_channels = all_addresses - addresses_with_channels

        self.info(
            f"Addresses without channels: {len(addresses_without_channels)}")

        for address in addresses_without_channels:
            AsyncLoop.add(NodeHelper.open_channel, self.address, self.api, address,
                          self.params.channel.fundingAmount, publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        if self.channels is None:
            return

        in_opens = [c for c in self.channels.incoming if c.status.is_open]

        for channel in in_opens:
            AsyncLoop.add(NodeHelper.close_channel,
                          self.address, self.api, channel, "incoming_closed", publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        if self.channels is None:
            return

        out_pendings = [
            c for c in self.channels.outgoing if c.status.is_pending]

        self.info(f"Pending channels: {len(out_pendings)}")

        for channel in out_pendings:
            AsyncLoop.add(NodeHelper.close_pending_channel,
                          self.address, self.api, channel, "pending_closed", publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def close_old_channels(self):
        """
        Close channels that have been open for too long.
        """
        if self.channels is None:
            return

        peer_history: dict[str, datetime] = await self.peer_history.get()
        to_peer_history = dict[str, datetime]()
        channels_to_close: list[str] = []

        address_to_channel = {
            c.destination_address: c
            for c in self.channels.outgoing
            if c.status.is_open
        }

        for address, channel in address_to_channel.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (
                datetime.now() - timestamp
            ).total_seconds() < self.params.channel.maxAgeSeconds:
                continue

            channels_to_close.append(channel)

        await self.peer_history.update(to_peer_history)
        self.debug(
            f"Updated peer history with {len(to_peer_history)} new entries")

        self.info(f"Closing {len(channels_to_close)} old channels")
        for channel in channels_to_close:
            AsyncLoop.add(NodeHelper.close_channel,
                          self.address, self.api, channel, "old_closed", publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        if self.channels is None:
            return

        out_opens = [c for c in self.channels.outgoing if c.status.is_open]

        low_balances = [
            c
            for c in out_opens
            if int(c.balance) / 1e18 <= self.params.channel.minBalance
        ]

        self.info(f"Low balance channels: {len(low_balances)}")

        peer_ids = [p.address.hopr for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                AsyncLoop.add(NodeHelper.fund_channel, self.address,
                              self.api, channel, self.params.channel.fundingAmount, publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
        results = await self.api.peers()
        peers = {Peer(item.peer_id, item.address, item.version)
                 for item in results}
        peers = {p for p in peers if not p.is_old(self.params.peer.minVersion)}

        addresses_w_timestamp = {p.address.native: datetime.now() for p in peers}

        await self.peers.set(peers)
        await self.peer_history.update(addresses_w_timestamp)

        self.info(f"Peers: {len(peers)}")

        if addr := self.address:
            PEERS_COUNT.labels(addr.hopr).set(len(peers))

    @master(flagguard, formalin, connectguard)
    async def retrieve_channels(self):
        """
        Retrieve all channels.
        """
        channels = await self.api.channels()

        if channels is None:
            self.warning("No channels found")
            return

        if not hasattr(channels, "incoming") or not hasattr(channels, "outgoing"):
            self.warning("No channels found")
            return

        if addr := self.address:
            channels.outgoing = [
                c
                for c in channels.all
                if c.source_peer_id == addr.hopr and not c.status.is_closed
            ]
            channels.incoming = [
                c
                for c in channels.all
                if c.destination_peer_id == addr.hopr and not c.status.is_closed
            ]

            self.channels = channels

            self.info(
                f"Channels: {len(channels.incoming)} in and {len(channels.outgoing)} out"
            )
            CHANNELS.labels(addr.hopr, "outgoing").set(len(channels.outgoing))
            CHANNELS.labels(addr.hopr, "incoming").set(len(channels.incoming))

    @master(flagguard, formalin, connectguard)
    async def get_total_channel_funds(self):
        """
        Retrieve total funds.
        """
        if self.address is None:
            return

        if self.channels is None:
            return

        results = await Utils.balanceInChannels(self.channels.outgoing)

        if self.address.hopr not in results:
            self.warning("Funding info not found")
            return

        funds = results[self.address.hopr].get("channels_balance", 0)

        self.info(f"Channels funds: {funds}")
        CHANNEL_FUNDS.labels(self.address.hopr).set(funds)

        return funds

    @master(flagguard, formalin, connectguard)
    async def observe_relayed_messages(self):
        """
        Check the inbox for messages.
        """
        if self.address is None:
            return

        for relayer, s in self.session_management.items():
            buffer_size: int = (
                self.params.sessions.packetSize * self.params.sessions.numPackets
            )
            messages = s.receive(buffer_size).decode().split("\n")
            MESSAGES_STATS.labels("relayed", self.address.hopr, relayer).inc(
                len(messages)
            )

    @master(flagguard, formalin, connectguard)
    async def observe_message_queue(self):
        message: MessageFormat = await MessageQueue().buffer.get()

        peers = [peer.address.hopr for peer in await self.peers.get()]
        channels = [channel.destination_peer_id for channel in self.channels.outgoing]

        for checklist in [peers, channels, self.session_management]:
            if message.relayer not in checklist:
                return

        self.session_management[message.relayer].send(message.bytes)

        MESSAGES_STATS.labels("sent", self.address.hopr, message.relayer).inc()
        
    @master(flagguard, formalin, connectguard)
    async def open_sessions(self):
        known_peers_addresses: set[Address] = set([peer.address for peer in await self.peers.get()])
        with_session_addresses = set(self.session_management.keys())
        without_session_addresses = known_peers_addresses - with_session_addresses
        
        for address in without_session_addresses:
            AsyncLoop.add(self.open_session, address, publish_to_task_set=False)


    async def open_session(self, relayer: Address):
        if session := await NodeHelper.open_session(self.address, self.api, relayer.address):
            self.session_management[relayer] = SessionToSocket(session)

    @master(flagguard, formalin, connectguard)
    async def close_sessions(self):
        active_sessions = await self.api.get_sessions(Protocol.UDP)

        to_remove = []
        for peer, s in self.session_management.items():
            if s.session in active_sessions:
                continue
            s.socket.close()
            to_remove.append(peer)        

        for peer in to_remove:
            AsyncLoop.add(NodeHelper.close_session, 
                self.address, self.api, peer, 
                self.session_management.pop(peer).session, 
                publish_to_task_set=False)
            
    
    @property
    def tasks(self):
        return [getattr(self, method) for method in Utils.decorated_methods(__file__, "formalin")]
