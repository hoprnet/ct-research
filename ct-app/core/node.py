import asyncio
import time
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.channelstatus import ChannelStatus
from .components.decorators import connectguard, flagguard, formalin
from .components.hoprd_api import MESSAGE_TAG, HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.peer import Peer

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
        self.address: Optional[Address] = None

        self.peers = LockedVar("peers", set[Peer]())
        self.outgoings = LockedVar("outgoings", [])
        self.incomings = LockedVar("incomings", [])
        self.connected = LockedVar("connected", False)

        self.peer_history = LockedVar("peer_history", dict[str, datetime]())

        self.params = Parameters()

        self.started = False

    def print_prefix(self):
        return ".".join(self.url.split("//")[-1].split(".")[:2])

    async def _retrieve_address(self):
        """
        Retrieve the address of the node.
        """
        address = await self.api.get_address("all")

        if not isinstance(address, dict):
            return

        if "hopr" not in address or "native" not in address:
            return

        self.address = Address(address["hopr"], address["native"])

    @flagguard
    @formalin(None)
    async def healthcheck(self):
        """
        Perform a healthcheck on the node.
        """
        health = await self.api.healthyz()
        await self.connected.set(health)
        self.debug(f"Connection state: {health}")

        if address := self.address:
            HEALTH.labels(address.id).set(int(health))

    @flagguard
    @formalin("Retrieving balances")
    @connectguard
    async def retrieve_balances(self):
        """
        Retrieve the balances of the node.
        """
        balances: dict = await self.api.balances()
        for token, balance in balances.items():
            BALANCE.labels(self.address.id, token).set(balance)

        return balances

    @flagguard
    @formalin("Opening channels")
    @connectguard
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        out_opens = [
            c
            for c in await self.outgoings.get()
            if not ChannelStatus.isClosed(c.status)
        ]

        addresses_with_channels = {c.destination_address for c in out_opens}
        all_addresses = {
            p.address.address
            for p in await self.peers.get()
            if not p.version_is_old(self.params.peer.min_version)
        }
        addresses_without_channels = all_addresses - addresses_with_channels

        self.debug(f"Addresses without channels: {len(addresses_without_channels)}")

        for address in addresses_without_channels:
            ok = await self.api.open_channel(
                address,
                f"{int(self.params.channel.funding_amount*1e18):d}",
            )
            if ok:
                self.debug(f"Opened channel to {address}")
                CHANNELS_OPENED.labels(self.address.id).inc()
            OPEN_CHANNELS_CALLS.labels(self.address.id).inc()

        ADDRESSES_WOUT_CHANNELS.labels(self.address.id).set(
            len(addresses_without_channels)
        )

    @flagguard
    @formalin("Closing incoming channels")
    @connectguard
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """

        in_opens = [
            c for c in await self.incomings.get() if ChannelStatus.isOpen(c.status)
        ]

        for channel in in_opens:
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.debug(f"Closed channel {channel.channel_id}")
                INCOMING_CHANNELS_CLOSED.labels(self.address.id).inc()
            CLOSE_INCOMING_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Closing pending channels")
    @connectguard
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        out_pendings = [
            c for c in await self.outgoings.get() if ChannelStatus.isPending(c.status)
        ]

        self.debug(f"Pending channels: {len(out_pendings)}")

        for channel in out_pendings:
            ok = await self.api.close_channel(channel.channel_id)
            if ok:
                self.debug(f"Closed pending channel {channel.channel_id}")
                PENDING_CHANNELS_CLOSED.labels(self.address.id).inc()
            CLOSE_PENDING_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Closing old channels")
    @connectguard
    async def close_old_channels(self):
        """
        Close channels that have been open for too long.
        """
        outgoings = await self.outgoings.get()
        peer_history: dict[str, datetime] = await self.peer_history.get()
        to_peer_history = dict[str, datetime]()
        channels_to_close: list[str] = []

        address_to_channel_id = {
            c.destination_address: c.channel_id
            for c in outgoings
            if ChannelStatus.isOpen(c.status)
        }

        for address, channel_id in address_to_channel_id.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (
                datetime.now() - timestamp
            ).total_seconds() < self.params.channel.max_age_seconds:
                continue

            channels_to_close.append(channel_id)

        await self.peer_history.update(to_peer_history)
        self.debug(f"Updated peer history with {len(to_peer_history)} new entries")

        self.info(f"Closing {len(channels_to_close)} old channels")
        for channel in channels_to_close:
            ok = await self.api.close_channel(channel)

            if ok:
                self.debug(f"Channel {channel} closed")
                OLD_CHANNELS_CLOSED.labels(self.address.id).inc()
            else:
                self.debug(f"Failed to close channel {channel_id}")

            CLOSE_OLD_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Funding channels")
    @connectguard
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        out_opens = [
            c for c in await self.outgoings.get() if ChannelStatus.isOpen(c.status)
        ]

        low_balances = [
            c
            for c in out_opens
            if int(c.balance) / 1e18 <= self.params.channel.min_balance
        ]

        self.debug(f"Low balance channels: {len(low_balances)}")

        peer_ids = [p.address.id for p in await self.peers.get()]

        for channel in low_balances:
            if channel.destination_peer_id in peer_ids:
                ok = await self.api.fund_channel(
                    channel.channel_id, self.params.channel.funding_amount * 1e18
                )
                if ok:
                    self.debug(f"Funded channel {channel.channel_id}")
                    FUNDED_CHANNELS.labels(self.address.id).inc()
                FUND_CHANNELS_CALLS.labels(self.address.id).inc()

    @flagguard
    @formalin("Retrieving peers")
    @connectguard
    async def retrieve_peers(self):
        """
        Retrieve real peers from the network.
        """
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

        self.debug(f"Peers: {len(peers)}")
        PEERS_COUNT.labels(self.address.id).set(len(peers))

    @flagguard
    @formalin("Retrieving outgoing channels")
    @connectguard
    async def retrieve_outgoing_channels(self):
        """
        Retrieve all outgoing channels.
        """
        channels = await self.api.all_channels(False)

        outgoings = [
            c
            for c in channels.all
            if c.source_peer_id == self.address.id
            and not ChannelStatus.isClosed(c.status)
        ]

        await self.outgoings.set(outgoings)
        self.debug(f"Outgoing channels: {len(outgoings)}")
        OUTGOING_CHANNELS.labels(self.address.id).set(len(outgoings))

    @flagguard
    @formalin("Retrieving incoming channels")
    @connectguard
    async def retrieve_incoming_channels(self):
        """
        Retrieve all incoming channels.
        """
        channels = await self.api.all_channels(False)

        incomings = [
            c
            for c in channels.all
            if c.destination_peer_id == self.address.id
            and not ChannelStatus.isClosed(c.status)
        ]

        await self.incomings.set(incomings)
        self.debug(f"Incoming channels: {len(incomings)}")
        INCOMING_CHANNELS.labels(self.address.id).set(len(incomings))

    @flagguard
    @formalin("Retrieving total funds")
    @connectguard
    async def get_total_channel_funds(self):
        """
        Retrieve total funds.
        """
        channels = await self.outgoings.get()

        results = await Utils.aggregatePeerBalanceInChannels(channels)

        if self.address.id not in results:
            return

        funds = results[self.address.id].get("channels_balance", 0)

        self.debug(f"Channels funds: {funds}")
        TOTAL_CHANNEL_FUNDS.labels(self.address.id).set(funds)

        return funds

    async def _delay_message(
        self,
        relayer: str,
        message: str,
        tag: int,
        sleep: float,
    ):
        await asyncio.sleep(sleep)

        return await self.api.send_message(self.address.id, message, [relayer], tag)

    async def distribute_rewards(
        self, peer_group: dict[str, dict[str, int]]
    ) -> dict[str, int]:
        # format of peer group is:
        #  {
        #     "0x1212": {
        #         "remaining": 10,
        #         "tag": 49,
        #         "ticket-price": 0.1,
        #         ...
        #     },
        #     ...
        # }

        issued_count = {peer_id: 0 for peer_id in peer_group.keys()}

        for relayer, data in peer_group.items():
            remaining = data.get("remaining", 0)
            tag = data.get("tag", None)
            ticket_price = data.get("ticket-price", None)

            if remaining == 0:
                continue

            if tag is None or ticket_price is None:
                self.error(
                    "Invalid peer in group when sending messages (missing data)"
                )  # should never happen
                continue

            channel_balance = await self.api.channel_balance(self.address.id, relayer)
            max_possible = int(min(remaining, channel_balance // ticket_price))

            if max_possible == 0:
                self.warning(
                    f"Channel balance to {relayer} doesn't allow to send any message"
                )
                continue

            tasks = set[asyncio.Task]()

            for it in range(max_possible):
                sleep = it * self.params.distribution.delay_between_two_messages
                message = f"{relayer}//{time.time()}-{it + 1}/{max_possible}"

                task = asyncio.create_task(
                    self._delay_message(
                        relayer,
                        message,
                        MESSAGE_TAG + tag,
                        sleep,
                    )
                )
                tasks.add(task)

            issued = await asyncio.gather(*tasks)
            issued_count[relayer] = sum(issued)

            self.debug(f"Sent {issued_count[relayer]} messages through {relayer}")

        return issued_count

    async def check_inbox(
        self, peer_group: dict[str, dict[str, int]]
    ) -> dict[str, int]:
        # format of peer group is:
        #  {
        #     "0x1212": {
        #         "remaining": 10,
        #         "tag": 49,
        #         "ticket-price": 0.1,
        #         ...
        #     },
        #     ...
        # }
        relayed_count = {peer_id: 0 for peer_id in peer_group.keys()}

        for relayer, data in peer_group.items():
            tag = data.get("tag", None)
            if tag is None:
                self.error(
                    "Invalid peer in group when querying inbox (missing tag)"
                )  # should never happen
                continue
            if not isinstance(tag, int):
                self.error(
                    f"Invalid peer in group when querying inbox (invalid tag: '{tag}')"
                )
                continue

            messages = await self.api.messages_pop_all(MESSAGE_TAG + tag)
            relayed_count[relayer] = len(messages)
            self.debug(f"{relayed_count[relayer]} messages relayed by {relayer}")

        return relayed_count

    def tasks(self):
        self.info("Starting node")
        return [
            asyncio.create_task(self.healthcheck()),
            asyncio.create_task(self.retrieve_peers()),
            asyncio.create_task(self.retrieve_outgoing_channels()),
            asyncio.create_task(self.retrieve_incoming_channels()),
            asyncio.create_task(self.retrieve_balances()),
            asyncio.create_task(self.open_channels()),
            asyncio.create_task(self.close_incoming_channels()),
            asyncio.create_task(self.close_pending_channels()),
            asyncio.create_task(self.close_old_channels()),
            asyncio.create_task(self.fund_channels()),
            asyncio.create_task(self.get_total_channel_funds()),
        ]

    def __str__(self):
        return f"Node(id='{self.url}')"

    @classmethod
    def fromAddressAndKeyLists(cls, addresses: list[str], keys: list[str]):
        return [cls(address, key) for address, key in zip(addresses, keys)]
