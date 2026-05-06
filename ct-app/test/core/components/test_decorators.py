import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from core.config_parser.base_classes import ExplicitParams, Flag
from core.components.decorators import connectguard, get_keepalive_methods, keepalive


@dataclass(init=False)
class FooClassParams(ExplicitParams):
    foo_keepalive_func: Flag


@dataclass(init=False)
class FooFlagParams(ExplicitParams):
    fooclass: FooClassParams


@dataclass(init=False)
class FooParams(ExplicitParams):
    flags: FooFlagParams


class FooClass:
    def __init__(self):
        self.connected = False
        self.running = False
        self.counter = 0
        self.params = FooParams({"flags": {"fooclass": {"foo_keepalive_func": 1}}})

    @connectguard
    async def foo_connectguard_func(self):
        return True

    @keepalive
    async def foo_keepalive_func(self):
        self.counter += 1
        await asyncio.sleep(0.1)


@pytest.fixture
def foo_class():
    return FooClass()


@pytest.mark.asyncio
async def test_connectguard(foo_class: FooClass, mocker):
    # Mock asyncio.sleep to avoid 15-second delay in connectguard decorator
    mocker.patch("core.components.decorators.asyncio.sleep", new=AsyncMock())

    foo_class.connected = False
    await foo_class.foo_connectguard_func()

    foo_class.connected = True
    res = await foo_class.foo_connectguard_func()
    assert res is True


@pytest.mark.asyncio
async def test_keepalive(foo_class: FooClass):
    async def setup_test(run_time: float, sleep_time: Flag, min_count: int):
        foo_class.params.flags.fooclass.foo_keepalive_func = sleep_time
        foo_class.counter = 0
        foo_class.running = True
        try:
            await asyncio.wait_for(
                asyncio.create_task(foo_class.foo_keepalive_func()), timeout=run_time
            )
        except asyncio.TimeoutError:
            pass

        assert foo_class.counter >= min_count

    await setup_test(1, Flag(0), 1)
    await setup_test(1.4, Flag(0.5), 1)


def test_get_keepalive_methods_returns_decorated_methods(foo_class: FooClass):
    setattr(foo_class.foo_keepalive_func.__func__, "_is_keepalive", True)
    methods = get_keepalive_methods(foo_class)
    names = sorted(method.__name__ for method in methods)
    assert names == ["foo_keepalive_func"]
