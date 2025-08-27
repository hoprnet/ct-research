import asyncio
import random

import pytest

from core.components import MessageQueue, Peer
from core.components.config_parser import Parameters

SECONDS_IN_YEAR = 365 * 24 * 60 * 60


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_time,min_range,max_range",
    [
        (
            round(random.random() * 2.0 + 0.1, 2),
            round(random.random() * 0.1 + 0.1, 2),
            round(random.random() * 0.3 + 0.2, 2),
        )
    ],
)
async def test_request_relay(exc_time: int, min_range: float, max_range: float):
    peers = {Peer(f"0x{num}") for num in range(10)}

    params = Parameters({"flags": {"peer": {"requestRelay": True}}})

    for peer in peers:
        rand_delay = round(random.random() * (max_range - min_range) + min_range, 1)
        peer.yearly_message_count = SECONDS_IN_YEAR / rand_delay

        peer.params = params
        peer.running = True

    await asyncio.sleep(exc_time)

    queue = MessageQueue()

    calls_and_delays = {p.address.native: {"calls": 0, "delay": p.message_delay} for p in peers}

    while queue.size > 0:
        calls_and_delays[await queue.get_async()]["calls"] += 1

    durations = [(values["calls"] + 1) * values["delay"] for values in calls_and_delays.values()]
    assert (max(durations) - min(durations)) < (max_range * 2)
