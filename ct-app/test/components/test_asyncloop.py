import asyncio

import pytest
from core.components import AsyncLoop


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
async def test_hasRunningTasks():
    assert not AsyncLoop.hasRunningTasks()

    AsyncLoop.add(foo_awaitable)
    assert AsyncLoop.hasRunningTasks()
