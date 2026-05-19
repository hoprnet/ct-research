from prometheus_client import Gauge

from ..components.decorators import keepalive
from ..services.network_update_coordinator import NetworkUpdateSource
from .peers_allocation import PeerAllocationMixin

REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])


class NetworkSyncMixin(PeerAllocationMixin):
    def _on_link_update(self) -> None:
        self.network_update_coordinator.request(NetworkUpdateSource.ACCOUNT_LINK_SUBSCRIPTION)
        self.channel_lifecycle_coordinator.request("account_link_subscription")

    async def subscribe_accounts(self):
        await self.network_sync_orchestrator.stream_link_updates(self._on_link_update)

    @keepalive
    async def refresh_balances(self):
        await self.network_sync_orchestrator.refresh_balances()
        self.network_update_coordinator.request(NetworkUpdateSource.SAFE_BALANCE_REFRESH)

    @keepalive
    async def refresh_redeemed(self):
        await self.network_sync_orchestrator.refresh_redeemed(self.peers)
        self.network_update_coordinator.request(NetworkUpdateSource.REDEEMED_REFRESH)
        for peer in self.peers.values():
            if peer.redeemed_amount is not None:
                REDEEMED_REWARDS.labels(peer.address.native).set(float(peer.redeemed_amount.value))
