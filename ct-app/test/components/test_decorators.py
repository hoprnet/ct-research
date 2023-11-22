import asyncio
import os
from core.components.flags import Flags

import pytest
from core.components.baseclass import Base
from core.components.decorators import connectguard, flagguard, formalin
from core.components.lockedvar import LockedVar


class FooClass(Base):
    flag_prefix = "FOO_"

    def __init__(self):
        super().__init__()
        self.connected = LockedVar("connected", False)
        self.started = False
        self.counter = 0

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
    Flags._cache_flags = None

    os.environ["FLAG_FOO_FOO_FLAGGUARD_FUNC"] = "1"
    res = await foo_class.foo_flagguard_func()
    assert res is True

    del os.environ["FLAG_FOO_FOO_FLAGGUARD_FUNC"]

@pytest.mark.asyncio
async def test_formalin(foo_class: FooClass):
    # reset flag cache and instance counter
    Flags._cache_flags = None
    foo_class.counter = 0
    # # # # # # # # # # # # # # # # # # # # 

    # should run only once
    os.environ["FLAG_FOO_FOO_FORMALIN_FUNC"] = "0"

    foo_class.started = True
    asyncio.create_task(foo_class.foo_formalin_func())
    await asyncio.sleep(1)
    foo_class.started = False
    await asyncio.sleep(0.5)

    assert foo_class.counter == 1 # counter increased only once

    del os.environ["FLAG_FOO_FOO_FORMALIN_FUNC"]

    # reset flag cache and instance counter
    Flags._cache_flags = None
    foo_class.counter = 0
    # # # # # # # # # # # # # # # # # # # # 

    # should run twice (every 0.5s in 1.1s)
    os.environ["FLAG_FOO_FOO_FORMALIN_FUNC"] = "0.5"
    
    foo_class.started = True
    asyncio.create_task(foo_class.foo_formalin_func())
    await asyncio.sleep(1.1)
    foo_class.started = False
    await asyncio.sleep(0.5)
    
    assert foo_class.counter == 2 # counter increased twice
    
    del os.environ["FLAG_FOO_FOO_FORMALIN_FUNC"]

