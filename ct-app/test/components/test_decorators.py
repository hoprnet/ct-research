import asyncio
from copy import deepcopy

import pytest
from core.components.baseclass import Base
from core.components.decorators import connectguard, flagguard, formalin
from core.components.lockedvar import LockedVar
from core.components.parameters import Parameters

flag_dictionary = {
    "flags": {
        "fooclass": {
            "fooFlagguardFunc": 1,
            "fooFormalinFunc": 1
        }
    }
}

class FooClass(Base):
    def __init__(self):
        super().__init__()
        self.connected = LockedVar("connected", False)
        self.started = False
        self.counter = 0
        self.params = Parameters()

    @connectguard
    async def foo_connectguard_func(self):
        await asyncio.sleep(0.1)
        return True

    @flagguard
    async def foo_flagguard_func(self):
        await asyncio.sleep(0.1)
        return True

    @flagguard
    @formalin("Foo formalin")
    async def foo_formalin_func(self):
        self.counter += 1
        await asyncio.sleep(0.1)

@pytest.fixture
def foo_class():
    return FooClass()


@pytest.mark.asyncio
async def test_connectguard(foo_class: FooClass):
    await foo_class.connected.set(False)
    res = await foo_class.foo_connectguard_func()
    assert res is None

    await foo_class.connected.set(True)
    res = await foo_class.foo_connectguard_func()
    assert res is True


@pytest.mark.asyncio
async def test_flagguard(foo_class: FooClass):
    res = await foo_class.foo_flagguard_func()
    assert res is None

    # delete flag cache so that new flags are retrieved from env
    foo_class.params.parse(flag_dictionary)

    res = await foo_class.foo_flagguard_func()
    assert res is True

@pytest.mark.asyncio
async def test_flagguard_missing_flags(foo_class: FooClass):
    # reset instance counter
    flags = deepcopy(flag_dictionary)
    # # # # # # # # # # # # # # # # # # # #

    # should not run
    del flags["flags"]["fooclass"]["fooFlagguardFunc"]

    foo_class.params.parse(flags)

    with pytest.raises(AttributeError):
        await foo_class.foo_flagguard_func()


    # reset instance counter
    flags = deepcopy(flag_dictionary)
    foo_class.params = Parameters()
    # # # # # # # # # # # # # # # # # # # #

    del flags["flags"]["fooclass"]
    foo_class.params.parse(flags)

    with pytest.raises(AttributeError):
        await foo_class.foo_flagguard_func()


    # reset instance counter
    flags = deepcopy(flag_dictionary)
    foo_class.params = Parameters()
    # # # # # # # # # # # # # # # # # # # #

    foo_class.params.parse(flag_dictionary)
    foo_class.params.flags.fooclass.fooFlagguardFunc = None

    await foo_class.foo_flagguard_func()

    assert foo_class.counter == 0  # counter increased only once


@pytest.mark.asyncio
async def test_formalin(foo_class: FooClass):
    # reset instance counter
    foo_class.counter = 0
    # # # # # # # # # # # # # # # # # # # #

    # should run only once
    foo_class.params.parse(flag_dictionary)
    foo_class.params.flags.fooclass.fooFormalinFunc = 0

    foo_class.started = True
    asyncio.create_task(foo_class.foo_formalin_func())
    await asyncio.sleep(1)
    foo_class.started = False
    await asyncio.sleep(0.5)

    assert foo_class.counter == 1  # counter increased only once

    # reset instance counter
    foo_class.counter = 0
    # # # # # # # # # # # # # # # # # # # #

    # should run twice (every 0.5s in 1.1s)
    foo_class.params.flags.fooclass.fooFormalinFunc = 0.5

    foo_class.started = True
    asyncio.create_task(foo_class.foo_formalin_func())
    await asyncio.sleep(1.1)
    foo_class.started = False
    await asyncio.sleep(0.5)

    assert foo_class.counter == 2  # counter increased twice