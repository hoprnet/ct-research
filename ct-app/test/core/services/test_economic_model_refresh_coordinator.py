import asyncio

import pytest

from core.services.economic_model_refresh_coordinator import EconomicModelRefreshCoordinator


@pytest.mark.asyncio
async def test_request_coalesces_multiple_signals_into_sequential_refreshes():
    run_count = 0
    gate = asyncio.Event()

    async def refresh_callback():
        nonlocal run_count
        run_count += 1
        if run_count == 1:
            await gate.wait()

    coordinator = EconomicModelRefreshCoordinator(refresh_callback)

    coordinator.request()
    await asyncio.sleep(0)
    coordinator.request()
    gate.set()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert run_count == 2


@pytest.mark.asyncio
async def test_refresh_now_runs_callback_once():
    run_count = 0

    async def refresh_callback():
        nonlocal run_count
        run_count += 1

    coordinator = EconomicModelRefreshCoordinator(refresh_callback)
    await coordinator.refresh_now()

    assert run_count == 1
