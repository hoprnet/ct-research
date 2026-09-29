from datetime import datetime

from ..types.network_state import NetworkState
from ..types.network_updates import LinkUpdate


class LinkStateStore:
    """
    Node-to-safe links built from the Blokli account subscription.

    Each (re)connection resends a snapshot of all accounts but never mentions nodes that
    disappeared while disconnected. Every connection therefore starts a new generation; once its
    snapshot has been received, `sweep()` drops the links it did not resend.
    """

    def __init__(self, state: NetworkState):
        self.state = state
        self._generation = 0
        self._generation_of: dict[str, int] = {}

    def start_generation(self) -> None:
        self._generation += 1

    def apply_link_updates(self, updates: list[LinkUpdate]) -> None:
        for update in updates:
            if update.safe_address is None:
                self.state.node_to_safe.pop(update.node_address, None)
                self._generation_of.pop(update.node_address, None)
            else:
                self.state.node_to_safe[update.node_address] = update.safe_address
                self._generation_of[update.node_address] = self._generation
        self.state.last_links_refresh_at = datetime.now()

    def sweep(self) -> int:
        stale = [node for node, gen in self._generation_of.items() if gen < self._generation]
        for node_address in stale:
            self.state.node_to_safe.pop(node_address, None)
            self._generation_of.pop(node_address, None)
        return len(stale)
