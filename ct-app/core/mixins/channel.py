import logging
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge

from ..components.asyncloop import AsyncLoop
from ..components.balance import Balance
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.node_helper import NodeHelper
from ..components.utils import Utils
from .protocols import HasAPI, HasChannels, HasParams, HasPeers

CHANNELS = Gauge("ct_channels", "Node channels", ["direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")

configure_logging()
logger = logging.getLogger(__name__)


class ChannelMixin(HasAPI, HasChannels, HasParams, HasPeers):
    @property
    def outgoing_open_channels(self) -> list:
        """Cached list of open outgoing channels."""
        if self._cached_outgoing_open is None and self.channels:
            self._cached_outgoing_open = [c for c in self.channels.outgoing if c.status.is_open]
        return self._cached_outgoing_open or []

    @property
    def incoming_open_channels(self) -> list:
        """Cached list of open incoming channels."""
        if self._cached_incoming_open is None and self.channels:
            self._cached_incoming_open = [c for c in self.channels.incoming if c.status.is_open]
        return self._cached_incoming_open or []

    @property
    def outgoing_pending_channels(self) -> list:
        """Cached list of pending outgoing channels."""
        if self._cached_outgoing_pending is None and self.channels:
            self._cached_outgoing_pending = [
                c for c in self.channels.outgoing if c.status.is_pending
            ]
        return self._cached_outgoing_pending or []

    @property
    def outgoing_not_closed_channels(self) -> list:
        """Cached list of not-closed outgoing channels."""
        if self._cached_outgoing_not_closed is None and self.channels:
            self._cached_outgoing_not_closed = [
                c for c in self.channels.outgoing if not c.status.is_closed
            ]
        return self._cached_outgoing_not_closed or []

    @property
    def address_to_open_channel(self) -> dict:
        """Cached dict mapping destination address to open outgoing channel."""
        if self._cached_address_to_open_channel is None and self.channels:
            self._cached_address_to_open_channel = {
                c.destination: c
                for c in self.channels.outgoing
                if c.status.is_open and hasattr(c, "destination")
            }
        return self._cached_address_to_open_channel or {}

    def invalidate_channel_cache(self) -> None:
        """Invalidate all channel caches when channels are modified."""
        self._cached_outgoing_open = None
        self._cached_incoming_open = None
        self._cached_outgoing_pending = None
        self._cached_outgoing_not_closed = None
        self._cached_address_to_open_channel = None

    @master(keepalive, connectguard)
    async def get_total_channel_funds(self) -> Optional[Balance]:
        """
        Retrieve total funds.
        """
        if self.address is None:
            return None

        if self.channels is None:
            return None

        results: dict[str, Balance] = await Utils.balanceInChannels(self.channels.outgoing)

        balance: Balance = results.get(self.address.native, Balance.zero("wxHOPR"))

        logger.info(
            "Retrieved total amount stored in outgoing channels",
            {"amount": balance.as_str},
        )
        CHANNEL_FUNDS.set(balance.value)

        return balance

    @master(keepalive, connectguard)
    async def retrieve_channels(self):
        """
        Retrieve all channels.
        """
        channels = await self.api.channels()

        if channels is None:
            logger.warning("No results while retrieving channels")
            return

        if addr := self.address:
            channels.outgoing = [
                c for c in channels.all if c.source == addr.native and not c.status.is_closed
            ]
            channels.incoming = [
                c for c in channels.all if c.destination == addr.native and not c.status.is_closed
            ]

            self.channels = channels

            # Invalidate channel caches when channels are updated
            self.invalidate_channel_cache()

            CHANNELS.labels("outgoing").set(len(channels.outgoing))
            CHANNELS.labels("incoming").set(len(channels.incoming))

        incoming_count = len(channels.incoming) if channels else 0
        outgoing_count = len(channels.outgoing) if channels else 0

        logger.info(
            "Scanned channels linked to the node",
            {"incoming": incoming_count, "outgoing": outgoing_count},
        )

        self.topology_data = await Utils.balanceInChannels(channels.all)
        logger.info("Fetched all topology links", {"count": len(self.topology_data)})
        TOPOLOGY_SIZE.set(len(self.topology_data))

    @master(keepalive, connectguard)
    async def fund_channels(self):
        """
        Fund channels that are below minimum threshold.
        """
        if self.channels is None:
            return

        out_opens = self.outgoing_open_channels  # Use cached property
        low_balances = [c for c in out_opens if c.balance <= self.params.channel.min_balance]

        logger.debug(
            "Starting funding of channels where balance is too low",
            {"count": len(low_balances), "threshold": self.params.channel.min_balance.as_str},
        )

        addresses = [p.address.native for p in self.peers]

        for channel in low_balances:
            if channel.destination in addresses:
                AsyncLoop.add(
                    NodeHelper.fund_channel,
                    self.api,
                    channel,
                    self.params.channel.funding_amount,
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

        address_to_channel = self.address_to_open_channel  # Use cached property

        for address, channel in address_to_channel.items():
            timestamp = peer_history.get(address, None)

            if timestamp is None:
                to_peer_history[address] = datetime.now()
                continue

            if (
                datetime.now() - timestamp
            ).total_seconds() < self.params.channel.max_age_seconds.value:
                continue

            channels_to_close.append(channel)

        self.peer_history.update(to_peer_history)

        logger.debug(
            "Starting closure of dangling channels open with peer visible for too long",
            {"count": len(channels_to_close)},
        )

        for channel in channels_to_close:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.api,
                channel,
                "old_closed",
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
    async def close_pending_channels(self):
        """
        Close channels in PendingToClose state.
        """
        if self.channels is None:
            return

        out_pendings = self.outgoing_pending_channels  # Use cached property

        if len(out_pendings) > 0:
            logger.debug(
                "Starting closure of pending channels",
                {"count": len(out_pendings)},
            )

        for channel in out_pendings:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.api,
                channel,
                "pending_closed",
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
    async def close_incoming_channels(self):
        """
        Close incoming channels
        """
        if self.channels is None:
            return

        in_opens = self.incoming_open_channels  # Use cached property

        logger.debug(
            "Starting closure of incoming channels",
            {"count": len(in_opens)},
        )
        for channel in in_opens:
            AsyncLoop.add(
                NodeHelper.close_channel,
                self.api,
                channel,
                "incoming_closed",
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
    async def open_channels(self):
        """
        Open channels to discovered_peers.
        """
        if self.channels is None:
            return

        out_opens = self.outgoing_not_closed_channels  # Use cached property

        addresses_with_channels = {c.destination for c in out_opens}
        all_addresses = {p.address.native for p in self.peers}
        addresses_without_channels = all_addresses - addresses_with_channels

        logger.debug(
            "Starting opening of channels",
            {"count": len(addresses_without_channels)},
        )

        for address in addresses_without_channels:
            AsyncLoop.add(
                NodeHelper.open_channel,
                self.api,
                address,
                self.params.channel.funding_amount,
                publish_to_task_set=False,
            )
