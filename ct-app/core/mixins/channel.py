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

CHANNELS = Gauge("ct_channels", "Node channels", ["address", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels", ["address"])
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")

configure_logging()
logger = logging.getLogger(__name__)


class ChannelMixin(HasAPI, HasChannels, HasParams, HasPeers):
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
            {"amount": balance.as_str},
        )
        CHANNEL_FUNDS.labels(self.address.native).set(balance.value)

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

            CHANNELS.labels(addr.native, "outgoing").set(len(channels.outgoing))
            CHANNELS.labels(addr.native, "incoming").set(len(channels.incoming))

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

        out_opens = [c for c in self.channels.outgoing if c.status.is_open]
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

        out_pendings = [c for c in self.channels.outgoing if c.status.is_pending]

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

        in_opens = [c for c in self.channels.incoming if c.status.is_open]

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

        out_opens = [c for c in self.channels.outgoing if not c.status.is_closed]

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
