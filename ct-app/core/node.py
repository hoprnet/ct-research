# region Imports
import asyncio
import logging
import random
from datetime import datetime
from typing import Callable, Optional

from prometheus_client import Gauge

from .api import HoprdAPI, Protocol
from .components import LockedVar, Peer, Utils
from .components.address import Address
from .components.asyncloop import AsyncLoop
from .components.balance import Balance
from .components.config_parser import Parameters
from .components.decorators import connectguard, keepalive, master
from .components.logs import configure_logging
from .components.messages import MessageFormat, MessageQueue
from .components.node_helper import NodeHelper
from .components.pattern_matcher import PatternMatcher
from .components.session_to_socket import SessionToSocket

# endregion

# region Metrics
BALANCE = Gauge("ct_balance", "Node balance", ["address", "token"])
CHANNELS = Gauge("ct_channels", "Node channels", ["address", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels", ["address"])
HEALTH = Gauge("ct_node_health", "Node health", ["address"])
PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["address"])
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

        self.peers = set[Peer]()
        self.peer_history = dict[str, datetime]()

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
        addresses = await self.api.address()

        if addresses is None:
            logger.warning("No results while retrieving addresses", self.log_base_params)
            return
        self.address = Address(addresses.native)

        logger.debug("Retrieved addresses", self.log_base_params)

        return self.address

    async def _healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        health = await self.api.healthyz()
        self.connected = health

        if addr := await self.retrieve_address():
            HEALTH.labels(addr.native).set(int(health))
            if not health:
                logger.warning("Node is not reachable", self.log_base_params)
        else:
            logger.warning("No address found", self.log_base_params)

    @keepalive
    async def healthcheck(self):
        await self._healthcheck()

    @master(keepalive, connectguard)
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
                "Retrieved balances",
                {
                    **{key: str(value) for key, value in balances.as_dict.items()},
                    **self.log_base_params,
                },
            )
            for token, balance in vars(balances).items():
                if balance is None:
                    continue
                BALANCE.labels(addr.native, token).set(balance.value)

        return balances

    @master(keepalive, connectguard)
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        if self.channels is None:
            return

        out_opens = [c for c in self.channels.outgoing if not c.status.is_closed]

        addresses_with_channels = {c.destination for c in out_opens}
        all_addresses = {p.address.native for p in self.peers}
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
                self.params.channel.funding_amount,
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
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

    @master(keepalive, connectguard)
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

    @master(keepalive, connectguard)
    async def close_old_channels(self):
        """
        Close channels that have been open for too long.
        """
        if self.channels is None:
            return

        peer_history: dict[str, datetime] = self.peer_history
        to_peer_history = dict[str, datetime]()
        channels_to_close: list[str] = []

        address_to_channel = {c.destination: c for c in self.channels.outgoing if c.status.is_open}

        for address, channel in address_to_channel.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (datetime.now() - timestamp).total_seconds() < self.params.channel.max_age_seconds:
                continue

            channels_to_close.append(channel)

        self.peer_history.update(to_peer_history)

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

    @master(keepalive, connectguard)
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        if self.channels is None:
            return

        out_opens = [c for c in self.channels.outgoing if c.status.is_open]

        low_balances = [c for c in out_opens if c.balance <= self.params.channel.min_balance]

        logger.info(
            "Starting funding of channels where balance is too low",
            {
                "count": len(low_balances),
                "threshold": self.params.channel.min_balance.as_str,
                **self.log_base_params,
            },
        )

        addresses = [p.address.native for p in self.peers]

        for channel in low_balances:
            if channel.destination in addresses:
                AsyncLoop.add(
                    NodeHelper.fund_channel,
                    self.address,
                    self.api,
                    channel,
                    self.params.channel.funding_amount.as_str,
                    publish_to_task_set=False,
                )

    @master(keepalive, connectguard)
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

        self.peers = {Peer(item.address) for item in results}
        self.peer_history.update({item.address: datetime.now() for item in results})

        if addr := self.address:
            PEERS_COUNT.labels(addr.native).set(len(self.peers))

    @master(keepalive, connectguard)
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
                c for c in channels.all if c.source == addr.native and not c.status.is_closed
            ]
            channels.incoming = [
                c for c in channels.all if c.destination == addr.native and not c.status.is_closed
            ]

            self.channels = channels

            CHANNELS.labels(addr.native, "outgoing").set(len(channels.outgoing))
            CHANNELS.labels(addr.native, "incoming").set(len(channels.incoming))

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

    @master(keepalive, connectguard)
    async def get_total_channel_funds(self) -> Optional[Balance]:
        """
        Retrieve total funds.
        """
        if self.address is None:
            return

        if self.channels is None:
            return

        results: dict[str, Balance] = await Utils.balanceInChannels(self.channels.outgoing)

        balance: Balance = results.get(self.address.native, Balance.zero("wxHOPR"))

        logger.info(
            "Retrieved total amount stored in outgoing channels",
            {"amount": balance.as_str, **self.log_base_params},
        )
        CHANNEL_FUNDS.labels(self.address.native).set(balance.value)

        return balance

    @master(keepalive, connectguard)
    async def observe_message_queue(self):
        checklists = {
            "peers": [peer.address.native for peer in self.peers],
            "channels": [channel.destination for channel in self.channels.outgoing] if self.channels else [], "sessions": self.session_management}

        # check if one of the checklist is empty
        for key, checklist in checklists.items():
            if not checklist:
                logger.debug("Checklist is empty", {
                             "checklist": key, **self.log_base_params})
                await asyncio.sleep(5)
                return

        message: MessageFormat = await MessageQueue().get_async()

        for key, checklist in checklists.items():
            if message.relayer not in checklist:
                logger.warning(
                    "Message relayer not found in checklist",
                    {"relayer": message.relayer, "key": key, **self.log_base_params},
                )
                return

        sess_and_socket: SessionToSocket = self.session_management[message.relayer]
        message.sender = self.address.native
        message.packet_size = sess_and_socket.session.payload

        AsyncLoop.add(
            sess_and_socket.send,
            message,
            publish_to_task_set=False,
        )

    @keepalive
    async def observe_sockets(self):
        for sess_and_socket in self.session_management.values():
            if sess_and_socket.socket is None:
                continue

            AsyncLoop.add(
                sess_and_socket.receive,
                sess_and_socket.session.payload,
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
    async def close_sessions(self):
        active_sessions = await self.api.list_sessions(Protocol.UDP)

        to_remove = [
            address
            for address, s in self.session_management.items()
            if s.session not in active_sessions
        ]

        if len(to_remove) == 0:
            logging.info("No sessions to close", self.log_base_params)
        else:
            logging.info("Closing sessions", {"addresses": to_remove, **self.log_base_params})

        for address in to_remove:
            AsyncLoop.add(
                NodeHelper.close_session,
                self.address,
                self.api,
                address,
                self.session_management.pop(address),
                publish_to_task_set=False,
            )

    async def close_all_sessions(self):
        """
        Close all sessions without checking if they are active, or if a socket is associated.
        Also, doesn't remove the session from the session_management dict.
        This method should run on startup to clean up any old sessions.
        """
        active_sessions = await self.api.list_sessions(Protocol.UDP)

        for session in active_sessions:
            AsyncLoop.add(
                NodeHelper.close_session_blindly,
                self.address,
                self.api,
                session,
                publish_to_task_set=False,
            )

    async def open_sessions(self, allowed: list[Address], destinations: list[Address]):
        if self.channels is None:
            logger.warning("No channels found yet", self.log_base_params)
            return

        addresses_with_channels = set([c.destination for c in self.channels.outgoing])

        allowed_addresses = set([address.native for address in allowed])
        addresses_with_session = set(self.session_management.keys())
        addresses_without_session = allowed_addresses - addresses_with_session

        for address in addresses_without_session.intersection(addresses_with_channels):
            destination: Address = random.choice(list(set(destinations) - {self.address}))
            AsyncLoop.add(self.open_session, destination, address, publish_to_task_set=False)

    async def open_session(self, destination: Address, relayer: str):
        if session := await NodeHelper.open_session(
            self.address,
            self.api,
            destination,
            relayer,
            self.p2p_endpoint,
        ):
            self.session_management[relayer] = SessionToSocket(session, self.p2p_endpoint)

    @property
    def tasks(self) -> list[Callable]:
        return [getattr(self, method) for method in Utils.decorated_methods(__file__, "keepalive")]

    @property
    def p2p_endpoint(self):
        if hasattr(self, "_p2p_endpoint"):
            return self._p2p_endpoint

        target_url = "ctdapp-{}-node-{}-p2p.ctdapp.{}.hoprnet.link"
        patterns: list[PatternMatcher] = [
            PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)"),
            PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)-p2p-tcp", self.params.environment),
        ]

        for pattern in patterns:
            if groups := pattern.search(self.url):
                self._p2p_endpoint = target_url.format(*groups)
                break
        else:
            logger.warning(
                "No match found for p2p endpoint, using url",
                {"url": self.url, **self.log_base_params},
            )
            self._p2p_endpoint = self.url

        return self._p2p_endpoint
