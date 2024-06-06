import asyncio

import pytest

from core.components.lockedvar import LockedVar


@pytest.fixture
def locked_var() -> LockedVar:
    return LockedVar("test_var", 0)


@pytest.mark.asyncio
async def test_locked_var(locked_var: LockedVar):
    assert await locked_var.get() == 0
    await locked_var.inc(1)
    assert await locked_var.get() == 1


@pytest.mark.asyncio
async def test_locked_var_concurrent(locked_var: LockedVar):
    async def increment_locked_var(var: LockedVar, value: int):
        await var.inc(value)

    await asyncio.gather(*[increment_locked_var(locked_var, 1) for _ in range(10)])

    assert await locked_var.get() == 10


@pytest.mark.asyncio
async def test_locker_var_infer_type():
    locked_var = LockedVar("test_var", 0, infer_type=True)
    with pytest.raises(TypeError):
        await locked_var.set("string")

    locked_var = LockedVar("test_var", 0, infer_type=False)
    await locked_var.set("string")
    assert await locked_var.get() == "string"

@pytest.mark.asyncio
async def test_locked_var_inc_with_infer_type():
    locked_var = LockedVar("test_var", 0, infer_type=True)

    await locked_var.inc(1.0)

    assert await locked_var.get() == 1.0

@pytest.mark.asyncio
async def test_locked_var_update_with_infer_type():
    locked_var = LockedVar("test_var", {}, infer_type=True)

    await locked_var.update({"key": 1.0})
    assert (await locked_var.get())["key"] == 1.0

    with pytest.raises(TypeError):
        await locked_var.update(10)