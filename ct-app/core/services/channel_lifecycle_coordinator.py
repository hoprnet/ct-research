import logging
from collections.abc import Awaitable, Callable

from .base_drain_coordinator import BaseDrainCoordinator

logger = logging.getLogger(__name__)


class ChannelLifecycleCoordinator(BaseDrainCoordinator):
    def __init__(self, reconcile_callback: Callable[[], Awaitable[None]]):
        super().__init__(error_message="Channel lifecycle reconcile failed")
        self.reconcile_callback = reconcile_callback

    def request(self, source: str | None = None) -> None:
        logger.debug("Channel lifecycle refresh requested", {"source": source})
        super().request(source)

    async def run_once(self) -> None:
        await self.reconcile_callback()
