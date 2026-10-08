import logging

from prometheus_client import Gauge

from ..api.hoprd_api import HoprdAPI
from ..components.decorators import connectguard, keepalive, master
from ..services.network_update_coordinator import NetworkUpdateSource
from ..types.peer import Peer
from ..services.eligibility import qualifying_outgoing_channels
from .runtime_state import NodeRuntimeState

PEERS_COUNT = Gauge("ct_peers_count", "Node peers")
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])

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

    def reconcile_peer_channels(self) -> None:
        qualifying = qualifying_outgoing_channels(
            self.channel_graph.channels(), self.params.incentive.min_channel_balance
        )

        for peer in self.peers.values():
            peer.qualifying_channels = qualifying.get(peer.address.native, 0)
            channel_balance = self.outgoing_channel_balances.get(peer.address.native)
            if channel_balance is not None:
                peer.channel_balance = channel_balance

    def invalidate_peer_cache(self) -> None:
        self._cached_peer_addresses = None
        self._cached_reachable_destinations = None
