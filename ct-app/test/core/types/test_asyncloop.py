import asyncio

import pytest

from core.types.asyncloop import AsyncLoop


def clearAsyncLoopInstance(func):
    async def wrapper_func():
        # Do something before the function
        instance = AsyncLoop()
        AsyncLoop().tasks.clear()
        del instance
        await func()
        AsyncLoop.stop()
        AsyncLoop().tasks.clear()

    return wrapper_func


async def foo_awaitable():
    await asyncio.sleep(0.01)


async def bar_awaitable():
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_add():
    assert len(AsyncLoop().tasks) == 0

    AsyncLoop.add(foo_awaitable)
    assert len(AsyncLoop().tasks) == 1


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_update():
    assert len(AsyncLoop().tasks) == 0

    AsyncLoop.update({foo_awaitable, bar_awaitable})
    assert len(AsyncLoop().tasks) == 2


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_add_fire_and_forget_does_not_publish_task():
    task = AsyncLoop.add(foo_awaitable, publish_to_task_set=False)

    assert task is not None
    assert len(AsyncLoop().tasks) == 0

    await task


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_add_returns_none_when_callback_creation_fails():
    def explode():
        raise RuntimeError("boom")

    task = AsyncLoop.add(explode)

    assert task is None


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_gather_any_returns_results_in_order():
    results = await AsyncLoop.gather_any([foo_awaitable(), bar_awaitable()])

    assert results == [None, None]


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_gather_awaits_tracked_tasks_and_prunes_completed_entries():
    task = AsyncLoop.add(foo_awaitable)

    assert task is not None
    assert len(AsyncLoop().tasks) == 1

    await AsyncLoop.gather()

    assert task.done()
    assert len(AsyncLoop().tasks) == 0


@pytest.mark.asyncio
@clearAsyncLoopInstance
async def test_stop_cancels_tracked_tasks_and_cleans_task_set():
    started = asyncio.Event()

    async def wait_forever():
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            raise

    task = AsyncLoop.add(wait_forever)

    assert task is not None
    await started.wait()

    AsyncLoop.stop()
    await asyncio.gather(task, return_exceptions=True)

    assert task.cancelled()
    assert len(AsyncLoop().tasks) == 0


def test_run_executes_async_stop_callback_on_success():
    events: list[str] = []

    async def process():
        events.append("process")

    async def stop_callback():
        events.append("stop")

    AsyncLoop.run(process, stop_callback)

    assert events == ["process", "stop"]


def test_run_executes_stop_callback_when_process_raises():
    events: list[str] = []

    async def process():
        events.append("process")
        raise RuntimeError("boom")

    async def stop_callback():
        events.append("stop")

    with pytest.raises(RuntimeError, match="boom"):
        AsyncLoop.run(process, stop_callback)

    assert events == ["process", "stop"]


def test_run_in_thread_returns_started_thread_handle():
    started = asyncio.Event()

    async def callback():
        started.set()

    thread = AsyncLoop.run_in_thread(callback)

    assert thread is not None
    thread.join(timeout=1.0)
    assert started.is_set()
