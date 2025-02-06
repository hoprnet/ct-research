import asyncio
from signal import SIGINT, SIGTERM
from typing import Any, Callable, Optional

from core.baseclass import Base

from .singleton import Singleton


class AsyncLoop(Base, metaclass=Singleton):
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.tasks = set[asyncio.Task]()

        self.loop.add_signal_handler(SIGINT, self.stop)
        self.loop.add_signal_handler(SIGTERM, self.stop)

    @classmethod
    def run(cls, process: Callable, stop_callback: Callable):
        try:
            cls().loop.run_until_complete(process())
        except asyncio.CancelledError:
            cls().error("Stopping the instance...")
        finally:
            stop_callback()
            cls().stop()

    @classmethod
    async def update(cls, tasks: set[Callable]):
        for task in tasks:
            await cls().add(task)

    @classmethod
    async def add(cls, callback: Callable, *args, publish_to_task_set: bool = True, get_result = False) -> Optional[Any]:
        try:
            task = asyncio.ensure_future(callback(*args))
        except Exception as e:
            cls().error(f"Failed to create task for {callback.__name__}: {e}")
            return
            
        if publish_to_task_set:
            cls().tasks.add(task)
        else:
            task.add_done_callback(lambda t: t.cancel() if not t.done() else None)

        if get_result:
            return await task

    @classmethod
    async def gather(cls):
        await asyncio.gather(*cls().tasks)

    @classmethod
    def stop(cls):
        for task in cls().tasks:
            task.add_done_callback(cls().tasks.discard)
            task.cancel()
