import logging
from datetime import datetime

from prometheus_client import Gauge

from ..api.hoprd_api import HoprdAPI
from ..components.decorators import connectguard, keepalive, master
from ..types.peer import Peer
from .peers_allocation import PeerAllocationMixin

PEERS_COUNT = Gauge("ct_peers_count", "Node peers")
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])

logger = logging.getLogger(__name__)


class PeerDiscoveryMixin(PeerAllocationMixin):
    api: HoprdAPI
    peer_history: dict[str, datetime]
    _cached_peer_addresses: set[str] | None
    _cached_reachable_destinations: set[str] | None

    @master(keepalive, connectguard)
    async def retrieve_peers(self):
        visible_peers: set[Peer] = {Peer(item.address) for item in await self.api.peers()}

        if len(visible_peers) == 0:
            logger.warning("No results while retrieving peers")
            return

        self.peer_history.update({item.address.native: datetime.now() for item in visible_peers})

        counts = {"new": 0, "known": 0, "unreachable": 0}

        visible_by_address = {peer.address.native: peer for peer in visible_peers}
        for address, peer in self.peers.items():
            if address in visible_by_address:
                if peer.yearly_message_count is None:
                    peer.yearly_message_count = 0
                counts["known"] += 1
            else:
                peer.yearly_message_count = None
                peer.running = False
                counts["unreachable"] += 1

        for address, peer in visible_by_address.items():
            if address not in self.peers:
                peer.yearly_message_count = 0
                self.peers[address] = peer
                counts["new"] += 1

        self.reconcile_peer_allocations()

        if counts["new"] > 0 or counts["unreachable"] > 0:
            self.invalidate_peer_cache()

        logger.info("Retrieved visible peers", counts)
        PEERS_COUNT.set(len(self.peers))
        for key, value in counts.items():
            UNIQUE_PEERS.labels(key).set(value)

    def invalidate_peer_cache(self) -> None:
        self._cached_peer_addresses = None
        self._cached_reachable_destinations = None
