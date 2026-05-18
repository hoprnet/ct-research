from prometheus_client import Gauge

from ..components.decorators import keepalive
from .peers_allocation import PeerAllocationMixin

REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])


class NetworkSyncMixin(PeerAllocationMixin):
    def _on_link_update(self) -> None:
        self.network_update_coordinator.request("account_link_subscription")
        self.channel_lifecycle_coordinator.request("account_link_subscription")

    async def subscribe_accounts(self):
        await self.network_sync_orchestrator.stream_link_updates(self._on_link_update)

    @keepalive
    async def refresh_balances(self):
        await self.network_sync_orchestrator.refresh_balances()
        self.network_update_coordinator.request("safe_balance_refresh")

    @keepalive
    async def refresh_redeemed(self):
        await self.network_sync_orchestrator.refresh_redeemed(self.peers)
        self.network_update_coordinator.request("redeemed_refresh")
        for peer in self.peers.values():
            if peer.redeemed_amount is not None:
                REDEEMED_REWARDS.labels(peer.address.native).set(float(peer.redeemed_amount.value))
