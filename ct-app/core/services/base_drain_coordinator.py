import asyncio
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseDrainCoordinator(ABC):
    def __init__(self, error_message: str | None = None):
        self._pending = False
        self._drain_task: asyncio.Task[None] | None = None
        self._error_message = error_message

    def request(self, source: str | None = None) -> None:
        self._on_request(source)
        self._pending = True
        if self._drain_task is not None and not self._drain_task.done():
            return
        self._drain_task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        while self._pending:
            self._pending = False
            try:
                await self.run_once()
            except Exception:
                if self._error_message is None:
                    raise
                logger.exception(self._error_message)
        self._on_idle()

    async def close(self) -> None:
        if self._drain_task is not None:
            await self._drain_task

    def _on_request(self, source: str | None) -> None:
        return

    def _on_idle(self) -> None:
        return

    @abstractmethod
    async def run_once(self) -> None:
        raise NotImplementedError
