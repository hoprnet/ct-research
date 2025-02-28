import asyncio

import pytest

from core.components.decorators import connectguard, flagguard, formalin
from core.components.parameters import ExplicitParams, Flag


class FooClassParams(ExplicitParams):
    keys = {
        "foo_flagguard_func": Flag,
        "foo_formalin_func": Flag,
    }


class FooFlagParams(ExplicitParams):
    keys = {
        "fooclass": FooClassParams,
    }


class FooParams(ExplicitParams):
    keys = {
        "flags": FooFlagParams,
    }

# FIXME: This whole file fails
# The problem is that the test is not properly mocking the Parameters class


class FooClass:
    def __init__(self):
        pass
        self.connected = False
        self.running = False
        self.counter = 0
        self.params = FooParams(
            {"flags": {"fooclass": {"foo_flagguard_func": 1, "foo_formalin_func": 1}}})

    @connectguard
    async def foo_connectguard_func(self):
        return True

    @flagguard
    async def foo_flagguard_func(self):
        return True

    @flagguard
    @formalin
    async def foo_formalin_func(self):
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
async def test_flagguard(foo_class: FooClass):
    foo_class.params.flags.fooclass.foo_flagguard_func = None
    assert await foo_class.foo_flagguard_func() is None

    foo_class.params.flags.fooclass.foo_flagguard_func = 1
    assert await foo_class.foo_flagguard_func() is True


@pytest.mark.asyncio
async def test_formalin(foo_class: FooClass):
    async def setup_test(run_time: float, sleep_time: float, expected_count: int):
        foo_class.params.flags.fooclass.foo_formalin_func = sleep_time
        foo_class.counter = 0
        foo_class.running = True
        try:
            await asyncio.wait_for(
                asyncio.create_task(foo_class.foo_formalin_func()), timeout=run_time
            )
        except asyncio.TimeoutError:
            pass

        assert foo_class.counter == expected_count

    await setup_test(1, 0, 10)
    await setup_test(1.4, 0.5, 3)
