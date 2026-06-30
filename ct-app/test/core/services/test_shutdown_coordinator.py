import pytest

from core.services.shutdown_coordinator import ShutdownCoordinator


@pytest.mark.asyncio
async def test_run_executes_registered_async_hooks():
    calls: list[str] = []

    async def hook_one():
        calls.append("one")

    async def hook_two():
        calls.append("two")

    coordinator = ShutdownCoordinator()
    coordinator.register_async("one", hook_one)
    coordinator.register_async("two", hook_two)

    await coordinator.run()

    assert sorted(calls) == ["one", "two"]
