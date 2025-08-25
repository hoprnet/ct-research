import logging
from datetime import datetime

from prometheus_client import Gauge

from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.peer import Peer
from .protocols import HasAPI, HasPeers

PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["address"])
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])

configure_logging()
logger = logging.getLogger(__name__)


class PeersMixin(HasAPI, HasPeers):
    @master(keepalive, connectguard)
    async def retrieve_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """
        visible_peers: set[Peer] = {Peer(item.address) for item in await self.api.peers()}

        if len(visible_peers) == 0:
            logger.warning("No results while retrieving peers")
            return

        self.peer_history.update({item.address.native: datetime.now() for item in visible_peers})

        counts = {"new": 0, "known": 0, "unreachable": 0}

        for peer in self.peers:
            # if peer is still visible
            if peer in visible_peers:
                if peer.yearly_message_count is None:
                    peer.yearly_message_count = 0
                    peer.start_async_processes()
                counts["known"] += 1

            # if peer is not visible anymore
            else:
                peer.yearly_message_count = None
                peer.running = False
                counts["unreachable"] += 1

        # if peer is new
        for peer in visible_peers:
            if peer not in self.peers:
                peer.params = self.params
                peer.yearly_message_count = 0
                peer.start_async_processes()
                self.peers.add(peer)
                counts["new"] += 1

        logger.info("Retrieved visible peers", counts)

        PEERS_COUNT.labels(self.address.native).set(len(self.peers))
        for key, value in counts.items():
            UNIQUE_PEERS.labels(key).set(value)
