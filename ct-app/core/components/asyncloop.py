import asyncio
from signal import SIGINT, SIGTERM
from typing import Callable

from .baseclass import Base
from .singleton import Singleton


class AsyncLoop(Base, metaclass=Singleton):
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.tasks = set[asyncio.Task]()

        self.loop.add_signal_handler(SIGINT, self.stop)
        self.loop.add_signal_handler(SIGTERM, self.stop)

    def run_until_complete(self, process: Callable):
        try:
            self.loop.run_until_complete(process())
        except asyncio.CancelledError:
            self.error("Stopping the instance...")
        finally:
            self.stop()

    def update(self, tasks: set[Callable]):
        for task in tasks:
            self.add(task)

    def add(self, callback: Callable):
        task = asyncio.create_task(callback())
        task.add_done_callback(self.tasks.discard)

        self.tasks.add(task)

    def foo(self, callback: Callable):
        task = asyncio.create_task(callback())
        task.add_done_callback(self.tasks.discard)

        asyncio.ensure_future(task, loop=self.loop)

    async def gather(self):
        return await asyncio.gather(*self.tasks)

    def stop(self):
        for task in self.tasks:
            task.cancel()

    @property
    def print_prefix(self) -> str:
        return "asyncloop"
