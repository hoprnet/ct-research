from prometheus_client import Gauge

from ..components.decorators import keepalive
from .peers_allocation import PeerAllocationMixin

REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])


class NetworkSyncMixin(PeerAllocationMixin):
    @keepalive
    async def subscribe_accounts(self):
        await self.network_sync_orchestrator.stream_link_updates(self.reconcile_peer_allocations)

    @keepalive
    async def refresh_balances(self):
        await self.network_sync_orchestrator.refresh_balances()
        self.reconcile_peer_allocations()

    @keepalive
    async def refresh_redeemed(self):
        await self.network_sync_orchestrator.refresh_redeemed(self.peers)
        for peer in self.peers.values():
            if peer.redeemed_amount is not None:
                REDEEMED_REWARDS.labels(peer.address.native).set(float(peer.redeemed_amount.value))
