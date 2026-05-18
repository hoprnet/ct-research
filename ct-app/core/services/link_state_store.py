from datetime import datetime

from ..types.network_state import NetworkState
from ..types.network_updates import LinkUpdate


class LinkStateStore:
    def __init__(self, state: NetworkState):
        self.state = state

    def apply_link_updates(self, updates: list[LinkUpdate]) -> None:
        for update in updates:
            self.state.node_to_safe[update.node_address] = update.safe_address
        self.state.last_links_refresh_at = datetime.now()
