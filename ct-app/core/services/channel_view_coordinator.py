import logging
from collections.abc import Awaitable, Callable

from .base_drain_coordinator import BaseDrainCoordinator

logger = logging.getLogger(__name__)


class ChannelViewCoordinator(BaseDrainCoordinator):
    """
    Rebuilds the node's channel views from the channel graph. Debounced, so a burst of channel
    events (e.g. the snapshot sent on each subscription connection) triggers a single rebuild.
    """

    def __init__(self, rebuild_callback: Callable[[], Awaitable[None]]):
        super().__init__(error_message="Channel view rebuild failed", debounce_seconds=0.5)
        self.rebuild_callback = rebuild_callback

    def request(self, source: str | None = None) -> None:
        logger.debug("Channel view rebuild requested", {"source": source})
        super().request(source)

    async def run_once(self) -> None:
        await self.rebuild_callback()
