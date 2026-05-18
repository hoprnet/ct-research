from datetime import datetime
import logging

from ..types.network_state import NetworkState
from ..types.peer import Peer
from ..types.network_updates import BalanceUpdate, LinkUpdate, RedeemedUpdate
from .link_state_store import LinkStateStore
from .blokli_repository import NetworkRepository

logger = logging.getLogger(__name__)


class NetworkStateService:
    def __init__(self, state: NetworkState, repository: NetworkRepository):
        self.state = state
        self.repository = repository
        self.link_state_store = LinkStateStore(state)

    def make_link_update(self, node_address: str, safe_address: str) -> LinkUpdate:
        return LinkUpdate(node_address=node_address, safe_address=safe_address)

    def make_balance_update(self, safe_address: str, balance) -> BalanceUpdate:
        return BalanceUpdate(safe_address=safe_address, balance=balance)

    def make_redeemed_update(
        self,
        peer_address: str,
        safe_address: str,
        node_address: str,
        redeemed_amount,
    ) -> RedeemedUpdate:
        return RedeemedUpdate(
            node_address=node_address,
            safe_address=safe_address,
            peer_address=peer_address,
            redeemed_amount=redeemed_amount,
        )

    def apply_link_updates(self, updates: list[LinkUpdate]) -> None:
        self.link_state_store.apply_link_updates(updates)
        logger.debug("Applied link updates", {"count": len(updates)})

    def apply_balance_updates(self, updates: list[BalanceUpdate]) -> None:
        for update in updates:
            self.state.safe_balances[update.safe_address] = update.balance
        self.state.last_balances_refresh_at = datetime.now()
        logger.info(
            "Safe balances updated",
            {"updated_count": len(updates), "tracked_safes": len(self.state.safe_balances)},
        )

    def apply_redeemed_updates(
        self,
        updates: list[RedeemedUpdate],
        peers: dict[str, Peer],
    ) -> None:
        for update in updates:
            peer = peers.get(update.peer_address)
            if peer is None:
                logger.warning(
                    "Skipping redeemed update for missing peer",
                    {"peer_address": update.peer_address, "safe_address": update.safe_address},
                )
                continue
            peer.redeemed_amount = update.redeemed_amount
        logger.debug("Applied redeemed updates", {"count": len(updates)})

    async def refresh_balances(self) -> None:
        safe_addresses = sorted(set(self.state.node_to_safe.values()))
        if not safe_addresses:
            logger.debug("Skipping safe balance refresh: no known safe links")
            return
        balances = await self.repository.get_safe_balances(safe_addresses)
        updates = [
            self.make_balance_update(snapshot.safe_address, snapshot.balance)
            for snapshot in balances
        ]
        if len(updates) < len(safe_addresses):
            logger.warning(
                "Incomplete safe balance refresh",
                {"requested": len(safe_addresses), "received": len(updates)},
            )
        self.apply_balance_updates(updates)
