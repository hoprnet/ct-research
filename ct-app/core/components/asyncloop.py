import asyncio
import logging
import threading
from signal import SIGINT, SIGTERM
from typing import Any, Callable, Iterable

from ..components.logs import configure_logging
from .singleton import Singleton

configure_logging()
logger = logging.getLogger(__name__)


class AsyncLoop(metaclass=Singleton):
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.tasks: set[asyncio.Task] = set()

        self.loop.add_signal_handler(SIGINT, self.stop)
        self.loop.add_signal_handler(SIGTERM, self.stop)

    @classmethod
    def run(cls, process: Callable, stop_callback: Callable):
        try:
            cls().loop.run_until_complete(process())
        except asyncio.CancelledError:
            logger.error("Stopping the instance")
        finally:
            # Handle both sync and async stop callbacks
            if asyncio.iscoroutinefunction(stop_callback):
                cls().loop.run_until_complete(stop_callback())
            else:
                stop_callback()
            cls().stop()

    @classmethod
    def update(cls, tasks: Iterable[Callable]):
        for task in tasks:
            cls().add(task)

    @classmethod
    def add(cls, callback: Callable, *args, publish_to_task_set: bool = True):
        try:
            task = asyncio.ensure_future(callback(*args))
        except Exception as err:
            logger.error(
                "Failed to create task",
                {
                    "task": getattr(callback, "__name__", str(callback)),
                    "error": str(err),
                },
            )
            return

        if publish_to_task_set:
            cls().tasks.add(task)
        else:
            # Fire-and-forget tasks: log exceptions but don't crash
            def _log_task_result(t):
                try:
                    t.result()  # Retrieve result to surface exceptions
                except asyncio.CancelledError:
                    pass  # Expected during shutdown
                except Exception as e:
                    logger.error(
                        "Background task failed",
                        {
                            "task": getattr(callback, "__name__", str(callback)),
                            "error": str(e),
                        },
                    )
            
            task.add_done_callback(_log_task_result)

    @classmethod
    def run_in_thread(cls, callback: Callable, *args):
        def sync_wrapper(callback, *args):
            try:
                asyncio.run(callback(*args))
            except Exception as err:
                logger.error(
                    "Failed to run task",
                    {"task": callback.__name__, "error": str(err)},
                )

        threading.Thread(target=sync_wrapper, args=(callback, *args), daemon=True).start()

    @classmethod
    async def gather(cls):
        await asyncio.gather(*cls().tasks)

    @classmethod
    async def gather_any(cls, futures: list[asyncio.Future]) -> tuple[Any]:
        return await asyncio.gather(*futures)

    @classmethod
    def stop(cls):
        for task in cls().tasks:
            task.add_done_callback(cls().tasks.discard)
            task.cancel()
