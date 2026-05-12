import asyncio
from collections.abc import Awaitable, Callable

from .base_drain_coordinator import BaseDrainCoordinator


class EconomicModelRefreshCoordinator(BaseDrainCoordinator):
    def __init__(self, refresh_callback: Callable[[], Awaitable[None]]):
        super().__init__(error_message="Economic model refresh failed")
        self.refresh_callback = refresh_callback
        self._lock = asyncio.Lock()

    async def refresh_now(self) -> None:
        async with self._lock:
            await self.refresh_callback()

    def request(self, source: str | None = None) -> None:
        super().request(source)

    async def run_once(self) -> None:
        await self.refresh_now()
