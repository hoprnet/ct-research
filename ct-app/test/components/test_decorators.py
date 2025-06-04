import asyncio
from dataclasses import dataclass

import pytest

from core.components.config_parser.base_classes import ExplicitParams, Flag
from core.components.decorators import connectguard, keepalive


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
async def test_connectguard(foo_class: FooClass):
    foo_class.connected = False
    res = await foo_class.foo_connectguard_func()
    assert res is None

    foo_class.connected = True
    res = await foo_class.foo_connectguard_func()
    assert res is True


@pytest.mark.asyncio
async def test_keepalive(foo_class: FooClass):
    async def setup_test(run_time: float, sleep_time: Flag, expected_count: int):
        foo_class.params.flags.fooclass.foo_keepalive_func = sleep_time
        foo_class.counter = 0
        foo_class.running = True
        try:
            await asyncio.wait_for(
                asyncio.create_task(foo_class.foo_keepalive_func()), timeout=run_time
            )
        except asyncio.TimeoutError:
            pass

        assert foo_class.counter == expected_count

    await setup_test(1, Flag(0), 10)
    await setup_test(1.4, Flag(0.5), 3)
