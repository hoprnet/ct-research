import asyncio
import logging
from collections.abc import Callable

from ..blokli.blokli_provider import ProviderError
from ..services.network_state_service import NetworkStateService
from ..services.blokli_repository import NetworkRepository
from ..types.peer import Peer

logger = logging.getLogger(__name__)


class NetworkSyncOrchestrator:
    def __init__(
        self,
        repository: NetworkRepository,
        state_service: NetworkStateService,
    ):
        self.repository = repository
        self.state_service = state_service

    async def stream_link_updates(self, on_update: Callable[[], None] | None = None) -> None:
        logger.info("Starting account subscription stream for node-safe links")
        while True:
            try:
                async for link in self.repository.stream_node_safe_links():
                    updates = [
                        self.state_service.make_link_update(link.node_address, link.safe_address),
                    ]
                    self.state_service.apply_link_updates(updates)
                    logger.debug(
                        "Applied node-safe link update",
                        {"node_address": link.node_address, "safe_address": link.safe_address},
                    )
                    if on_update is not None:
                        on_update()
            except ProviderError as error:
                logger.warning("Account subscription failed; retrying", {"error": str(error)})
                await asyncio.sleep(5)

    async def refresh_balances(self) -> None:
        await self.state_service.refresh_balances()
        logger.debug("Refreshed safe balances")

    async def refresh_redeemed(self, peers: dict[str, Peer]) -> None:
        if not peers:
            logger.debug("Skipping redeemed refresh: no peers available")
            return

        semaphore = asyncio.Semaphore(5)

        async def fetch_one(peer: Peer) -> None:
            if peer.safe_address is None:
                return
            async with semaphore:
                redemption = await self.repository.get_redeemed_amount(
                    safe_address=peer.safe_address,
                    node_address=peer.node_address,
                )
                update = self.state_service.make_redeemed_update(
                    peer.address.native,
                    peer.safe_address,
                    peer.node_address,
                    redemption.redeemed_amount,
                )
                self.state_service.apply_redeemed_updates([update], peers)

        await asyncio.gather(*(fetch_one(peer) for peer in peers.values()))
        logger.debug("Refreshed redeemed amounts", {"peer_count": len(peers)})
