import pytest
from core.components import LockedVar


@pytest.fixture
def locked_var() -> LockedVar:
    return LockedVar("test_var", 0)


@pytest.mark.asyncio
async def test_locker_var_infer_type():
    locked_var = LockedVar("test_var", 0, infer_type=True)
    with pytest.raises(TypeError):
        await locked_var.set("string")

    locked_var = LockedVar("test_var", 0, infer_type=False)
    await locked_var.set("string")
    assert await locked_var.get() == "string"


@pytest.mark.asyncio
async def test_locked_var_update_with_infer_type():
    locked_var = LockedVar("test_var", {}, infer_type=True)

    await locked_var.update({"key": 1.0})
    assert (await locked_var.get())["key"] == 1.0

    with pytest.raises(TypeError):
        await locked_var.update(10)
