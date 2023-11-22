import asyncio

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

    @connectguard
    async def foo_connectguard_func(self):
        await asyncio.sleep(0.5)

    @flagguard
    async def foo_flagguard_func(self):
        await asyncio.sleep(0.5)

    @flagguard
    @formalin("Foo formalin")
    async def foo_formalin_func(self):
        await asyncio.sleep(0.5)


@pytest.fixture
def foo_class():
    return FooClass()


@pytest.mark.asyncio
async def test_connectguard(foo_class: FooClass):
    await foo_class.foo_connectguard_func()
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_flagguard(foo_class: FooClass):
    await foo_class.foo_flagguard_func()
    pytest.skip("Not implemented")


@pytest.mark.asyncio
async def test_formalin(foo_class: FooClass):
    await foo_class.foo_formalin_func()
    pytest.skip("Not implemented")
