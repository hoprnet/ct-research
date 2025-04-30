# region Imports
import asyncio
import logging
import re
from datetime import datetime

from prometheus_client import Gauge, Histogram

from core.components.asyncloop import AsyncLoop
from core.components.logs import configure_logging

from .api import HoprdAPI, Protocol
from .components import LockedVar, Parameters, Peer, Utils
from .components.address import Address
from .components.decorators import connectguard, flagguard, formalin, master
from .components.messages import MessageFormat, MessageQueue
from .components.node_helper import NodeHelper
from .components.session_to_socket import SessionToSocket

# endregion

# region Metrics
BALANCE = Gauge("ct_balance", "Node balance", ["peer_id", "token"])
CHANNELS = Gauge("ct_channels", "Node channels", ["peer_id", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels", ["peer_id"])
HEALTH = Gauge("ct_node_health", "Node health", ["peer_id"])
MESSAGES_DELAYS = Histogram(
    "ct_messages_delays",
    "Messages delays",
    ["sender", "relayer"],
    buckets=[0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5],
)
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
        self.session_management = dict[str, SessionToSocket]()

        self.connected = False
        self.running = True

    @property
    def log_base_params(self):
        return {
            "host": self.url,
            "address": getattr(self.address, "native", None),
            "peer_id": getattr(self.address, "hopr", None),
        }

    @property
    async def safe_address(self):
        if self._safe_address is None:
            if info := await self.api.node_info():
                self._safe_address = info.hopr_node_safe
                logger.info(
                    "Retrieved safe address",
                    {"safe": self._safe_address, **self.log_base_params},
                )

        return self._safe_address

    async def retrieve_address(self):
        """
        Retrieve the address of the node.
        """
        addresses = await self.api.get_address()

        if addresses is None:
            logger.warning(
                "No results while retrieving addresses", self.log_base_params
            )
            return
        self.address = Address(addresses.hopr, addresses.native)

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
            logger.warning("No results while retrieving balances", self.log_base_params)
            return None

        if addr := self.address:
            logger.debug(
                "Retrieved balances", {**vars(balances), **self.log_base_params}
            )
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

        out_opens = [c for c in self.channels.outgoing if not c.status.is_closed]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {
            p.address.native
            for p in await self.peers.get()
            if not p.is_old(self.params.peer.minVersion)
        }
        addresses_without_channels = all_addresses - addresses_with_channels

        logger.info(
            "Starting opening of channels",
            {"count": len(addresses_without_channels), **self.log_base_params},
        )

        for address in addresses_without_channels:
            AsyncLoop.add(
                NodeHelper.open_channel,
                self.address,
                self.api,
                address,
                self.params.channel.fundingAmount,
                publish_to_task_set=False,
            )

    @master(flagguard, formalin, connectguard)
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        if self.channels is None:
            return

        in_opens = [c for c in self.channels.incoming if c.status.is_open]

        logger.info(
            "Starting closure of incoming channels",
            {"count": len(in_opens), **self.log_base_params},
        )
        for channel in in_opens:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.address,
                self.api,
                channel,
                "incoming_closed",
                publish_to_task_set=False,
            )

    @master(flagguard, formalin, connectguard)
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        if self.channels is None:
            return

        out_pendings = [c for c in self.channels.outgoing if c.status.is_pending]

        if len(out_pendings) > 0:
            logger.info(
                "Starting closure of pending channels",
                {"count": len(out_pendings), **self.log_base_params},
            )

        for channel in out_pendings:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.address,
                self.api,
                channel,
                "pending_closed",
                publish_to_task_set=False,
            )

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
            c.destination_address: c for c in self.channels.outgoing if c.status.is_open
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

        logger.info(
            "Starting closure of dangling channels open with peer visible for too long",
            {"count": len(channels_to_close), **self.log_base_params},
        )

        for channel in channels_to_close:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.address,
                self.api,
                channel,
                "old_closed",
                publish_to_task_set=False,
            )

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

        logger.info(
            "Starting funding of channels where balance is too low",
            {
                "count": len(low_balances),
                "threshold": self.params.channel.minBalance,
                **self.log_base_params,
            },
        )

        peer_ids = [p.address.hopr for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                AsyncLoop.add(
                    NodeHelper.fund_channel,
                    self.address,
                    self.api,
                    channel,
                    self.params.channel.fundingAmount,
                    publish_to_task_set=False,
                )

    @master(flagguard, formalin, connectguard)
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
        results = await self.api.peers()

        if len(results) == 0:
            logger.warning("No results while retrieving peers", self.log_base_params)
            return
        else:
            logger.info(
                "Scanned reachable peers",
                {"count": len(results), **self.log_base_params},
            )
        peers = {Peer(item.peer_id, item.address, item.version) for item in results}
        peers = {p for p in peers if not p.is_old(self.params.peer.minVersion)}

        addresses_w_timestamp = {p.address.native: datetime.now() for p in peers}

        await self.peers.set(peers)
        await self.peer_history.update(addresses_w_timestamp)

        if addr := self.address:
            PEERS_COUNT.labels(addr.hopr).set(len(peers))

    @master(flagguard, formalin, connectguard)
    async def retrieve_channels(self):
        """
        Retrieve all channels.
        """
        channels = await self.api.channels()

        if channels is None:
            logger.warning("No results while retrieving channels", self.log_base_params)
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

        logger.info(
            "Scanned channels linked to the node",
            {
                "incoming": incoming_count,
                "outgoing": outgoing_count,
                **self.log_base_params,
            },
        )

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

        logger.info(
            "Retrieved total amount stored in outgoing channels",
            {"amount": total, **self.log_base_params},
        )
        CHANNEL_FUNDS.labels(self.address.hopr).set(total)

        return total

    @master(flagguard, formalin, connectguard)
    async def observe_relayed_messages(self):
        """
        Check the inbox for messages.
        """
        if self.address is None:
            return

        for _, s in self.session_management.items():
            buffer_size: int = (
                self.params.sessions.packetSize * self.params.sessions.numPackets
            )
            messages = s.receive(buffer_size)

            if messages is None:
                continue

            for m in messages:
                try:
                    message = MessageFormat.parse(m)
                except ValueError as err:
                    logger.error(
                        "Error while parsing message",
                        {"error": err, **self.log_base_params},
                    )
                    continue

                if message.timestamp and message.relayer:
                    rtt = (
                        int(datetime.now().timestamp() * 1000) - message.timestamp
                    ) / 1000

                    MESSAGES_DELAYS.labels(self.address.hopr, message.relayer).observe(
                        rtt
                    )
                    MESSAGES_STATS.labels(
                        "relayed", self.address.hopr, message.relayer
                    ).inc()

    @master(flagguard, formalin, connectguard)
    async def observe_message_queue(self):
        message: MessageFormat = await MessageQueue().get_async()
        # TODO: maybe set the timestamp here ?

        if self.channels is None:
            logger.warning("No channels found yet")
            await asyncio.sleep(5)
            return

        peers = [peer.address.hopr for peer in await self.peers.get()]
        channels = [channel.destination_peer_id for channel in self.channels.outgoing]

        for checklist in [peers, channels, self.session_management]:
            if message.relayer not in checklist:
                return

        for _ in range(message.multiplier):
            self.session_management[message.relayer].send(message.bytes())
            message.increase_inner_index()

        MESSAGES_STATS.labels("sent", self.address.hopr, message.relayer).inc(
            message.multiplier
        )

    @master(flagguard, formalin, connectguard)
    async def close_sessions(self):
        active_sessions = await self.api.get_sessions(Protocol.UDP)

        to_remove = [
            peer_id
            for peer_id, s in self.session_management.items()
            if s.session not in active_sessions
        ]

        for peer_id in to_remove:
            AsyncLoop.add(
                NodeHelper.close_session,
                self.address,
                self.api,
                peer_id,
                self.session_management.pop(peer_id),
                publish_to_task_set=False,
            )

    async def close_sessions_blindly(self):
        """
        Close all sessions without checking if they are active, or if a socket is associated.
        Also, doesn't remove the session from the session_management dict.
        This method should run on startup to clean up any old sessions.
        """
        active_sessions = await self.api.get_sessions(Protocol.UDP)

        for session in active_sessions:
            AsyncLoop.add(
                NodeHelper.close_session_blindly,
                self.address,
                self.api,
                session,
                publish_to_task_set=False,
            )

    async def open_sessions(self, allowed_addresses: list[Address]):
        if self.channels is None:
            logger.warning("No channels found yet", self.log_base_params)
            return

        peer_ids_with_channels = set(
            [c.destination_peer_id for c in self.channels.outgoing]
        )

        allowed_peer_ids = set([address.hopr for address in allowed_addresses])
        peer_ids_with_session = set(self.session_management.keys())
        without_session_peer_ids = peer_ids_with_channels.intersection(
            allowed_peer_ids - peer_ids_with_session
        )

        for peer_id in without_session_peer_ids:
            AsyncLoop.add(self.open_session, peer_id, publish_to_task_set=False)

    async def open_session(self, relayer: str):
        if session := await NodeHelper.open_session(
            self.address,
            self.api,
            relayer,
            self.p2p_endpoint,
        ):
            self.session_management[relayer] = SessionToSocket(
                session,
                self.p2p_endpoint,
            )

    @property
    def tasks(self):
        return [
            getattr(self, method)
            for method in Utils.decorated_methods(__file__, "formalin")
        ]

    @property
    def p2p_endpoint(self):
        if hasattr(self, "_p2p_endpoint"):
            return self._p2p_endpoint

        if match := re.search(
            r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)", self.url
        ):
            deployment, index, environment = match.groups()
            self._p2p_endpoint = f"ctdapp-{deployment}-node-{index}-p2p.ctdapp.{environment}.hoprnet.link"
        elif match := re.search(r"ctdapp-([a-zA-Z]+)-node-(\d+)-p2p-tcp", self.url):
            deployment, index = match.groups()
            environment = self.params.environment
            self._p2p_endpoint = f"ctdapp-{deployment}-node-{index}-p2p.ctdapp.{environment}.hoprnet.link"
        else:
            self._p2p_endpoint = self.url
            logger.warning(
                "No match found for p2p endpoint, using url",
                {"url": self.url, **self.log_base_params},
            )

        return self._p2p_endpoint
