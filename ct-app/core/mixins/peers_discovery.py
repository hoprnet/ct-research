import asyncio
import logging

from prometheus_client import Gauge

from ..api.hoprd_api import HoprdAPI
from ..components.decorators import connectguard, keepalive, master
from ..constants.blokli import SNAPSHOT_SWEEP_DELAY_SECONDS
from ..services.network_update_coordinator import NetworkUpdateSource
from ..types.asyncloop import AsyncLoop
from ..types.network_models import NodeAddressUpdate
from ..types.peer import Peer
from ..services.eligibility import qualifying_outgoing_channels
from .runtime_state import NodeRuntimeState

PEERS_COUNT = Gauge("ct_peers_count", "Node peers")
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])
NODE_ADDRESSES_KNOWN = Gauge("ct_node_addresses_known", "Nodes with a known public IP")

logger = logging.getLogger(__name__)


class PeerDiscoveryMixin(NodeRuntimeState):
    api: HoprdAPI
    _cached_peer_addresses: set[str] | None
    _cached_reachable_destinations: set[str] | None

    @master(keepalive, connectguard)
    async def retrieve_peers(self):
        visible_peers: set[Peer] = {Peer(item.address) for item in await self.api.peers()}

        if len(visible_peers) == 0:
            logger.warning("No results while retrieving peers")
            return

        counts = {"new": 0, "known": 0, "unreachable": 0}

        visible_by_address = {peer.address.native: peer for peer in visible_peers}
        for address, peer in self.peers.items():
            if address in visible_by_address:
                peer.reachable = True
                counts["known"] += 1
            else:
                peer.reachable = False
                counts["unreachable"] += 1

        for address, peer in visible_by_address.items():
            if address not in self.peers:
                self.peers[address] = peer
                counts["new"] += 1

        self.network_update_coordinator.request(NetworkUpdateSource.PEER_DISCOVERY_REFRESH)

        if counts["new"] > 0 or counts["unreachable"] > 0:
            self.invalidate_peer_cache()

        logger.info("Retrieved visible peers", counts)
        PEERS_COUNT.set(len(self.peers))
        for key, value in counts.items():
            UNIQUE_PEERS.labels(key).set(value)

    async def subscribe_node_addresses(self) -> None:
        """Feed the node-address store from the Blokli node-address subscription."""
        logger.info("Starting node address subscription")
        while True:
            try:
                async for update in self.blokli_repository.stream_node_addresses(
                    on_connect=self._on_node_addresses_connect
                ):
                    self.apply_node_address_update(update)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Node address subscription failed; retrying", {"error": str(error)})
                await asyncio.sleep(5)

    def apply_node_address_update(self, update: NodeAddressUpdate) -> None:
        self.node_address_store.apply(update.address, update.ip)
        NODE_ADDRESSES_KNOWN.set(len(self.node_address_store))
        self.network_update_coordinator.request(NetworkUpdateSource.NODE_ADDRESSES_SUBSCRIPTION)

    def _on_node_addresses_connect(self) -> None:
        self.node_address_store.start_generation()
        if self._node_address_sweep_task is not None:
            self._node_address_sweep_task.cancel()

        async def _sweep() -> None:
            await asyncio.sleep(SNAPSHOT_SWEEP_DELAY_SECONDS)
            dropped = self.node_address_store.sweep()
            if dropped:
                logger.info("Dropped node addresses gone while disconnected", {"count": dropped})
                NODE_ADDRESSES_KNOWN.set(len(self.node_address_store))
                self.network_update_coordinator.request(
                    NetworkUpdateSource.NODE_ADDRESSES_SUBSCRIPTION
                )

        self._node_address_sweep_task = AsyncLoop.add(_sweep, publish_to_task_set=False)

    async def close_node_address_sweep(self) -> None:
        task = self._node_address_sweep_task
        self._node_address_sweep_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def reconcile_peer_channels(self) -> None:
        qualifying = qualifying_outgoing_channels(
            self.channel_graph.channels(), self.params.incentive.min_channel_balance
        )

        for peer in self.peers.values():
            peer.qualifying_channels = qualifying.get(peer.address.native, 0)
            channel_balance = self.outgoing_channel_balances.get(peer.address.native)
            if channel_balance is not None:
                peer.channel_balance = channel_balance
            peer.ip = self.node_address_store.ip_for(peer.address.native)

    def invalidate_peer_cache(self) -> None:
        self._cached_peer_addresses = None
        self._cached_reachable_destinations = None
