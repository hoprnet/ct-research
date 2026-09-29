from datetime import datetime

from prometheus_client import Gauge

from ..types.network_state import NetworkState
from ..types.network_updates import LinkUpdate
from .snapshot_generations import SnapshotGenerations

NODE_SAFE_LINKS = Gauge("ct_node_safe_links", "Number of nodes linked to a safe")


class LinkStateStore:
    """
    Node-to-safe links built from the Blokli account subscription. `sweep()` drops the links the
    latest connection's snapshot did not resend.
    """

    def __init__(self, state: NetworkState):
        self.state = state
        self._generations = SnapshotGenerations[str]()

    def start_generation(self) -> None:
        self._generations.start()

    def apply_link_updates(self, updates: list[LinkUpdate]) -> None:
        for update in updates:
            if update.safe_address is None:
                self.state.node_to_safe.pop(update.node_address, None)
                self._generations.forget(update.node_address)
            else:
                self.state.node_to_safe[update.node_address] = update.safe_address
                self._generations.touch(update.node_address)
        self.state.last_links_refresh_at = datetime.now()
        NODE_SAFE_LINKS.set(len(self.state.node_to_safe))

    def sweep(self) -> int:
        stale = self._generations.pop_stale()
        for node_address in stale:
            self.state.node_to_safe.pop(node_address, None)
        NODE_SAFE_LINKS.set(len(self.state.node_to_safe))
        return len(stale)
