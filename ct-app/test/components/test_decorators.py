import asyncio

import pytest

from core.components import LockedVar, Parameters
from core.components.decorators import connectguard, flagguard, formalin

flag_dictionary = {"flags": {"fooclass": {"fooFlagguardFunc": 1, "fooFormalinFunc": 1}}}


class FooClass:
    def __init__(self):
        pass
        self.connected = LockedVar("connected", False)
        self.running = False
        self.counter = 0
        self.params = Parameters()
        self.params.parse(flag_dictionary)

    @connectguard
    async def foo_connectguard_func(self):
        await asyncio.sleep(0.1)
        return True

    @flagguard
    async def foo_flagguard_func(self):
        await asyncio.sleep(0.1)
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
    foo_class.params.flags.fooclass.fooFlagguardFunc = None
    assert await foo_class.foo_flagguard_func() is None

    foo_class.params.flags.fooclass.fooFlagguardFunc = 1
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

    await setup_test(1, 0, 1)
    await setup_test(1.3, 0.5, 2)
