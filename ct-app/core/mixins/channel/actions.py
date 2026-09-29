import asyncio
import logging

from prometheus_client import Gauge

from ...api.response_objects import Channels
from ...components.utils import Utils
from ...constants.blokli import SNAPSHOT_SWEEP_DELAY_SECONDS
from ...services.network_update_coordinator import NetworkUpdateSource
from ...types.asyncloop import AsyncLoop
from ...types.balance import Balance
from ...types.network_models import ChannelGraphUpdate
from .cache import ChannelCacheMixin

CHANNELS = Gauge("ct_channels", "Node channels", ["direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
CHANNEL_GRAPH_SIZE = Gauge("ct_channel_graph_channels", "Non-closed channels in the channel graph")

logger = logging.getLogger(__name__)


class ChannelActionMixin(ChannelCacheMixin):
    """
    Read-only view of the channels, fed by the Blokli channel graph subscription. Opening,
    funding and closing channels is left to the node's own channel strategy; CT only needs to
    know which relays it can use and how much stake sits in the network.
    """

    async def subscribe_channels(self) -> None:
        logger.info("Starting channel graph subscription")
        while True:
            try:
                async for update in self.blokli_repository.stream_channel_graph(
                    on_connect=self._on_channel_graph_connect
                ):
                    self.apply_channel_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Channel graph subscription failed; retrying", {"error": str(error)})
                await asyncio.sleep(5)

    def apply_channel_update(self, update: ChannelGraphUpdate) -> None:
        self.channel_graph.apply(update)
        self.channel_view_coordinator.request("channel_graph_update")

    def _on_channel_graph_connect(self) -> None:
        self.channel_graph.start_generation()
        if self._channel_graph_sweep_task is not None:
            self._channel_graph_sweep_task.cancel()

        async def _sweep() -> None:
            await asyncio.sleep(SNAPSHOT_SWEEP_DELAY_SECONDS)
            dropped = self.channel_graph.sweep()
            if dropped:
                logger.info("Dropped channels closed while disconnected", {"count": dropped})
                self.channel_view_coordinator.request("channel_graph_sweep")

        self._channel_graph_sweep_task = AsyncLoop.add(_sweep, publish_to_task_set=False)

    async def rebuild_channel_views(self) -> None:
        all_channels = self.channel_graph.channels()
        CHANNEL_GRAPH_SIZE.set(len(all_channels))
        channels = Channels({})
        channels.all = all_channels

        own_address = self.address.native if self.address else None
        channels.outgoing = [c for c in all_channels if c.source == own_address]
        channels.incoming = [c for c in all_channels if c.destination == own_address]
        self.channels = channels
        self.invalidate_channel_cache()

        CHANNELS.labels("outgoing").set(len(channels.outgoing))
        CHANNELS.labels("incoming").set(len(channels.incoming))
        own_funds = sum(
            (c.balance for c in channels.outgoing if c.status.is_open), Balance.zero("wxHOPR")
        )
        CHANNEL_FUNDS.set(float(own_funds.value))

        self.outgoing_channel_balances = await Utils.balanceInChannels(all_channels)
        self.network_state.outgoing_channel_balances = dict(self.outgoing_channel_balances)
        TOPOLOGY_SIZE.set(len(self.outgoing_channel_balances))
        self.network_update_coordinator.request(NetworkUpdateSource.CHANNEL_TOPOLOGY_REFRESH)

        logger.info(
            "Rebuilt channel views",
            {
                "channels": len(all_channels),
                "incoming": len(channels.incoming),
                "outgoing": len(channels.outgoing),
            },
        )

    async def close_channel_graph_sweep(self) -> None:
        task = self._channel_graph_sweep_task
        self._channel_graph_sweep_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
