import logging
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge

from ...types.asyncloop import AsyncLoop
from ...types.balance import Balance
from ...components.decorators import connectguard, keepalive, master
from ...components.node_helper import NodeHelper
from ...components.utils import Utils
from .cache import ChannelCacheMixin

CHANNELS = Gauge("ct_channels", "Node channels", ["direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")

logger = logging.getLogger(__name__)


class ChannelActionMixin(ChannelCacheMixin):
    def _schedule_channel_operation(self, callback, *args) -> None:
        AsyncLoop.add(callback, *args, publish_to_task_set=False)

    @master(keepalive, connectguard)
    async def get_total_channel_funds(self) -> Optional[Balance]:
        if self.address is None or self.channels is None:
            return None

        results: dict[str, Balance] = await Utils.balanceInChannels(self.channels.outgoing)
        balance: Balance = results.get(self.address.native, Balance.zero("wxHOPR"))

        logger.info(
            "Retrieved total amount stored in outgoing channels",
            {"amount": balance.as_str},
        )
        CHANNEL_FUNDS.set(float(balance.value))
        return balance

    @master(keepalive, connectguard)
    async def retrieve_channels(self):
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
            self.invalidate_channel_cache()
            CHANNELS.labels("outgoing").set(len(channels.outgoing))
            CHANNELS.labels("incoming").set(len(channels.incoming))

        logger.info(
            "Scanned channels linked to the node",
            {"incoming": len(channels.incoming), "outgoing": len(channels.outgoing)},
        )

        self.outgoing_channel_balances = await Utils.balanceInChannels(channels.all)
        self.network_state.outgoing_channel_balances = dict(self.outgoing_channel_balances)
        logger.info(
            "Fetched all topology links",
            {"count": len(self.outgoing_channel_balances)},
        )
        TOPOLOGY_SIZE.set(len(self.outgoing_channel_balances))

    @master(keepalive, connectguard)
    async def fund_channels(self):
        if self.channels is None:
            return

        low_balances = [
            c for c in self.outgoing_open_channels if c.balance <= self.params.channel.min_balance
        ]
        logger.debug(
            "Starting funding of channels where balance is too low",
            {"count": len(low_balances), "threshold": self.params.channel.min_balance.as_str},
        )
        if low_balances:
            logger.info("Scheduling channel funding operations", {"count": len(low_balances)})

        peer_addresses = set(self.peers.keys())
        for channel in low_balances:
            if channel.destination in peer_addresses:
                self._schedule_channel_operation(
                    NodeHelper.fund_channel,
                    self.api,
                    channel,
                    self.params.channel.funding_amount,
                )

    @master(keepalive, connectguard)
    async def close_old_channels(self):
        if self.channels is None:
            return

        new_history_entries = dict[str, datetime]()
        channels_to_close = []

        for address, channel in self.address_to_open_channel.items():
            timestamp = self.peer_history.get(address)
            if timestamp is None:
                new_history_entries[address] = datetime.now()
                continue
            if (datetime.now() - timestamp).total_seconds() < self.params.channel.max_age.value:
                continue
            channels_to_close.append(channel)

        self.peer_history.update(new_history_entries)
        logger.debug(
            "Starting closure of dangling channels open with peer visible for too long",
            {"count": len(channels_to_close)},
        )
        if channels_to_close:
            logger.info("Scheduling old channel closures", {"count": len(channels_to_close)})

        for channel in channels_to_close:
            self._schedule_channel_operation(
                NodeHelper.close_channel,
                self.api,
                channel,
                "old_closed",
            )

    @master(keepalive, connectguard)
    async def close_pending_channels(self):
        if self.channels is None:
            return

        if self.outgoing_pending_channels:
            logger.debug(
                "Starting closure of pending channels",
                {"count": len(self.outgoing_pending_channels)},
            )
            logger.info(
                "Scheduling pending channel closures",
                {"count": len(self.outgoing_pending_channels)},
            )

        for channel in self.outgoing_pending_channels:
            self._schedule_channel_operation(
                NodeHelper.close_channel,
                self.api,
                channel,
                "pending_closed",
            )

    @master(keepalive, connectguard)
    async def close_incoming_channels(self):
        if self.channels is None:
            return

        logger.debug(
            "Starting closure of incoming channels",
            {"count": len(self.incoming_open_channels)},
        )
        if self.incoming_open_channels:
            logger.info(
                "Scheduling incoming channel closures",
                {"count": len(self.incoming_open_channels)},
            )
        for channel in self.incoming_open_channels:
            self._schedule_channel_operation(
                NodeHelper.close_channel,
                self.api,
                channel,
                "incoming_closed",
            )

    @master(keepalive, connectguard)
    async def open_channels(self):
        if self.channels is None:
            return

        addresses_with_channels = {
            address
            for channel in self.outgoing_not_closed_channels
            for address in [
                getattr(channel, "destination", None) or getattr(channel, "peer_address", None)
            ]
            if address is not None
        }
        addresses_without_channels = {
            p.address.native for p in self.peers.values()
        } - addresses_with_channels

        logger.debug("Starting opening of channels", {"count": len(addresses_without_channels)})
        if addresses_without_channels:
            logger.info(
                "Scheduling channel opens",
                {"count": len(addresses_without_channels)},
            )

        for address in addresses_without_channels:
            self._schedule_channel_operation(
                NodeHelper.open_channel,
                self.api,
                address,
                self.params.channel.funding_amount,
            )
