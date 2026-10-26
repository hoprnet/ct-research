import asyncio
from collections.abc import Awaitable, Callable


class ShutdownCoordinator:
    def __init__(self):
        self._hooks: list[tuple[str, Callable[[], Awaitable[None]]]] = []

    def register_async(self, name: str, callback: Callable[[], Awaitable[None]]) -> None:
        self._hooks.append((name, callback))

    async def run(self) -> None:
        if not self._hooks:
            return
        await asyncio.gather(
            *(callback() for _name, callback in self._hooks),
            return_exceptions=True,
        )
