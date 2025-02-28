# region Imports
import logging
from datetime import datetime

from prometheus_client import Gauge, Histogram

from core.components.asyncloop import AsyncLoop
from core.components.logs import configure_logging

from .api import HoprdAPI
from .components import LockedVar, Parameters, Peer, Utils
from .components.decorators import connectguard, flagguard, formalin, master
from .components.messages import MessageFormat, MessageQueue
from .components.node_helper import NodeHelper

# endregion

# region Metrics
BALANCE = Gauge("ct_balance", "Node balance", ["peer_id", "token"])
CHANNELS = Gauge("ct_channels", "Node channels", ["peer_id", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds",
                      "Total funds in out. channels", ["peer_id"])
HEALTH = Gauge("ct_node_health", "Node health", ["peer_id"])
MESSAGES_DELAYS = Histogram("ct_messages_delays", "Messages delays", ["sender", "relayer"], buckets=[
                            0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5])
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "sender", "relayer"])
PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["peer_id"])
# endregion

configure_logging()
logger = logging.getLogger(__name__)


class Node:
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
        self.connected = False
        self.running = False

    @property
    def log_base_params(self):
        return {"host": self.url,
                "address": getattr(self.address, "native", None),
                "peer_id": getattr(self.address, "hopr", None)}

    @property
    async def safe_address(self):
        if self._safe_address is None:
            if info := await self.api.node_info():
                self._safe_address = info.hopr_node_safe
                logger.info("Retrieved safe address", {"safe": self._safe_address,
                                                       **self.log_base_params})

        return self._safe_address

    async def retrieve_address(self):
        """
        Retrieve the address of the node.
        """
        addresses = await self.api.get_address()

        if addresses is None:
            logger.warning(
                "No results while retrieving addresses", self.log_base_params)
            return

        self.address = addresses
        logger.debug("Retrieved addresses", self.log_base_params)

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
                logger.warning("Node is not reachable", self.log_base_params)
        else:
            logger.warning("No address found", self.log_base_params)

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
            logger.warning("No results while retrieving balances",
                           self.log_base_params)
            return None

        if addr := self.address:
            logger.debug("Retrieved balances", {
                         **vars(balances), **self.log_base_params})
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

        logger.info("Starting opening of channels",
                    {"count": len(addresses_without_channels), **self.log_base_params})

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

        logger.info("Starting closure of incoming channels", {
                    "count": len(in_opens), **self.log_base_params})
        for channel in in_opens:
            AsyncLoop.add(NodeHelper.close_incoming_channel,
                          self.address, self.api, channel, publish_to_task_set=False)

    @master(flagguard, formalin, connectguard)
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        if self.channels is None:
            return

        out_pendings = [
            c for c in self.channels.outgoing if c.status.is_pending]

        if len(out_pendings) > 0:
            logger.info("Starting closure of pending channels",
                        {"count": len(out_pendings), **self.log_base_params})

        for channel in out_pendings:
            AsyncLoop.add(NodeHelper.close_pending_channel,
                          self.address, self.api, channel, publish_to_task_set=False)

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

        address_to_channel_id = {
            c.destination_address: c.id
            for c in self.channels.outgoing
            if c.status.is_open
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

        logger.info("Starting closure of dangling channels open with peer visible for too long",
                    {"count": len(channels_to_close), **self.log_base_params})

        for channel in channels_to_close:
            AsyncLoop.add(NodeHelper.close_old_channel,
                          self.address, self.api, channel, publish_to_task_set=False)

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

        logger.info("Starting funding of channels where balance is too low",
                    {"count": len(low_balances), "threshold": self.params.channel.minBalance,
                     **self.log_base_params})

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

        addresses_w_timestamp = {
            p.address.native: datetime.now() for p in peers}

        await self.peers.set(peers)
        await self.peer_history.update(addresses_w_timestamp)

        logger.info("Scanned reachable peers", {
                    "count": len(peers), **self.log_base_params})

        if addr := self.address:
            PEERS_COUNT.labels(addr.hopr).set(len(peers))

    @master(flagguard, formalin, connectguard)
    async def retrieve_channels(self):
        """
        Retrieve all channels.
        """
        channels = await self.api.channels()

        if channels is None:
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

            CHANNELS.labels(addr.hopr, "outgoing").set(len(channels.outgoing))
            CHANNELS.labels(addr.hopr, "incoming").set(len(channels.incoming))

        incoming_count = len(channels.incoming) if channels else 0
        outgoing_count = len(channels.outgoing) if channels else 0

        logger.info("Scanned channels linked to the node",
                    {"incoming": incoming_count, "outgoing": outgoing_count, **self.log_base_params})

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

        total = results.get(self.address.hopr, {}).get("channels_balance", 0)

        logger.info("Retrieved total amount stored in outgoing channels",
                    {"amount": total, **self.log_base_params})
        CHANNEL_FUNDS.labels(self.address.hopr).set(total)

        return total

    @master(flagguard, formalin, connectguard)
    async def observe_relayed_messages(self):
        """
        Check the inbox for messages.
        """
        messages = await self.api.messages_pop_all()
        count = len(messages)

        if count and not count & (count - 1):
            logger.warning("Inbox might be full", {
                           "count": count, **self.log_base_params})

        for m in messages:
            try:
                message = MessageFormat.parse(m.body)
            except ValueError as err:
                logger.exception("Error while parsing message",
                                 {"error": err, **self.log_base_params})
                continue

            if message.timestamp and message.relayer:
                rtt = (m.timestamp - message.timestamp) / 1000

                MESSAGES_DELAYS.labels(
                    self.address.hopr, message.relayer).observe(rtt)
                MESSAGES_STATS.labels(
                    "relayed", self.address.hopr, message.relayer).inc()

    @master(flagguard, formalin, connectguard)
    async def observe_message_queue(self):
        message = await MessageQueue().get_async()
        # TODO: maybe set the timestamp here ?

        peers = [peer.address.hopr for peer in await self.peers.get()]

        if message.relayer not in peers:
            return

        if self.channels is None:
            return

        channels = [
            channel.destination_peer_id for channel in self.channels.outgoing]

        if message.relayer not in channels:
            return

        AsyncLoop.add(NodeHelper.send_message, self.address,
                      self.api, message, publish_to_task_set=False)
        MESSAGES_STATS.labels("sent", self.address.hopr,
                              message.relayer).inc(message.multiplier)

    async def tasks(self):
        callbacks = [
            self.healthcheck,
            self.retrieve_peers,
            self.retrieve_balances,
            self.retrieve_channels,
            self.open_channels,
            self.fund_channels,
            self.close_old_channels,
            self.close_incoming_channels,
            self.close_pending_channels,
            self.get_total_channel_funds,
            self.observe_message_queue,
            self.observe_relayed_messages,
        ]

        return callbacks

    @classmethod
    def fromCredentials(cls, addresses: list[str], keys: list[str]):
        return [cls(address, key) for address, key in zip(addresses, keys)]
