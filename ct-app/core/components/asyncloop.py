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

    @classmethod
    def hasRunningTasks(cls) -> bool:
        return bool(cls().tasks)

    @classmethod
    def run(cls, process: Callable):
        try:
            cls().loop.run_until_complete(process())
        except asyncio.CancelledError:
            cls().error("Stopping the instance...")
        finally:
            cls().stop()

    @classmethod
    def update(cls, tasks: set[Callable]):
        for task in tasks:
            cls().add(task)

    @classmethod
    def add(cls, callback: Callable) -> asyncio.Task:
        task = asyncio.ensure_future(callback())
        cls().tasks.add(task)

        return task

    @classmethod
    async def gather(cls):
        await asyncio.gather(*cls().tasks)

    @classmethod
    def stop(cls):
        for task in cls().tasks:
            task.add_done_callback(cls().tasks.discard)
            task.cancel()
