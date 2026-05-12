import asyncio

import pytest

from core.services.network_update_coordinator import NetworkUpdateCoordinator


@pytest.mark.asyncio
async def test_requests_are_coalesced_and_execute_callbacks_in_order():
    calls: list[str] = []

    def reconcile_callback():
        calls.append("reconcile")

    def economic_refresh_callback():
        calls.append("refresh")

    coordinator = NetworkUpdateCoordinator(reconcile_callback, economic_refresh_callback)

    coordinator.request("a")
    coordinator.request("b")

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert calls == ["reconcile", "refresh"]


@pytest.mark.asyncio
async def test_close_waits_for_inflight_drain():
    gate = asyncio.Event()
    calls = 0

    def reconcile_callback():
        nonlocal calls
        calls += 1

    def economic_refresh_callback():
        gate.set()

    coordinator = NetworkUpdateCoordinator(reconcile_callback, economic_refresh_callback)
    coordinator.request("x")
    await gate.wait()
    await coordinator.close()

    assert calls == 1
