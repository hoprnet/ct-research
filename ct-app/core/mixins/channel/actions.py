import logging
import asyncio
from datetime import datetime
from typing import Optional

from prometheus_client import Gauge

from ...types.asyncloop import AsyncLoop
from ...types.balance import Balance
from ...components.node_helper import NodeHelper
from ...components.utils import Utils
from .cache import ChannelCacheMixin

CHANNELS = Gauge("ct_channels", "Node channels", ["direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")

logger = logging.getLogger(__name__)


class ChannelActionMixin(ChannelCacheMixin):
    def _schedule_channel_operation(self, source: str, callback, *args) -> None:
        async def _execute() -> None:
            await callback(*args)
            self.channel_lifecycle_coordinator.request(source)

        AsyncLoop.add(_execute, publish_to_task_set=False)

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

    async def retrieve_channels(self):
        if not self.connected:
            logger.debug("Skipping channel retrieval while node is disconnected")
            return

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
        self.network_update_coordinator.request("channel_topology_refresh")
        logger.info(
            "Fetched all topology links",
            {"count": len(self.outgoing_channel_balances)},
        )
        TOPOLOGY_SIZE.set(len(self.outgoing_channel_balances))

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
                    "fund_channel",
                    NodeHelper.fund_channel,
                    self.api,
                    channel.destination,
                    self.params.channel.funding_amount,
                )

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
                "close_old_channel",
                NodeHelper.close_channel,
                self.api,
                channel.destination,
                "old_closed",
            )

    def _cancel_channel_reclose(self, address: str) -> None:
        task = self._pending_channel_reclose_tasks.pop(address, None)
        if task is not None:
            task.cancel()

    def _ensure_pending_reclose(self, address: str) -> None:
        task = self._pending_channel_reclose_tasks.get(address)
        if task is not None and not task.done():
            return

        async def _reclose() -> None:
            await asyncio.sleep(300)
            await NodeHelper.close_channel(self.api, address, "pending_closed_retry")
            self.channel_lifecycle_coordinator.request("pending_close_retry")

        self._pending_channel_reclose_tasks[address] = AsyncLoop.add(
            _reclose,
            publish_to_task_set=False,
        )

    async def close_pending_channels(self):
        if self.channels is None:
            return

        pending_addresses = {channel.destination for channel in self.outgoing_pending_channels}

        if pending_addresses:
            logger.debug(
                "Scheduling delayed re-close for pending channels",
                {"count": len(pending_addresses), "delay_seconds": 300},
            )

        for address in list(self._pending_channel_reclose_tasks):
            if address not in pending_addresses:
                self._cancel_channel_reclose(address)

        for address in pending_addresses:
            self._ensure_pending_reclose(address)

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
                "close_incoming_channel",
                NodeHelper.close_channel,
                self.api,
                channel.destination,
                "incoming_closed",
            )

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
                "open_channel",
                NodeHelper.open_channel,
                self.api,
                address,
                self.params.channel.funding_amount,
            )

    async def reconcile_channels_once(self) -> None:
        await self.retrieve_channels()
        if self.channels is None:
            return

        await self.open_channels()
        await self.fund_channels()
        await self.close_old_channels()
        await self.close_pending_channels()

    async def close_channel_reclose_tasks(self) -> None:
        tasks = list(self._pending_channel_reclose_tasks.values())
        self._pending_channel_reclose_tasks.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
