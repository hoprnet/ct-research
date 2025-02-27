import asyncio
import random

import pytest
from packaging.version import Version

from core.components import MessageQueue, Parameters, Peer

SECONDS_IN_YEAR = 365 * 24 * 60 * 60


def test_peer_version():
    peer = Peer("some_id", "some_address", "0.0.1")

    peer.version = "0.1.0-rc.1"
    assert peer.is_old("0.1.0-rc.2")
    assert peer.is_old(Version("0.1.0-rc.2"))

    peer.version = "0.1.0-rc.1"
    assert not peer.is_old("0.1.0-rc.0")
    assert not peer.is_old(Version("0.1.0-rc.0"))

    peer.version = "0.1.1"
    assert not peer.is_old("0.1.0-rc.3")
    assert not peer.is_old(Version("0.1.0-rc.3"))

    peer.version = "0.1.0-rc.1"
    assert not peer.is_old("0.1.0-rc.1")
    assert not peer.is_old(Version("0.1.0-rc.1"))

    peer.version = "2.0"
    assert not peer.is_old("2.0")
    assert not peer.is_old(Version("2.0"))

    peer.version = "2.0"
    assert peer.is_old("2.1")
    assert peer.is_old(Version("2.1"))

    peer.version = "2.0.7"
    assert not peer.is_old("2.0.7")
    assert not peer.is_old(Version("2.0.7"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_time,min_range,max_range",
    [
        (
            random.randint(5, 10),
            round(random.random() * 0.1 + 0.1, 1),
            round(random.random() * 0.3 + 0.2, 1),
        )
    ],
)
async def test_request_relay(exc_time: int, min_range: float, max_range: float):
    peers = {Peer(f"12D{num}", f"0x{num}", "2.1.0") for num in range(10)}

    params = Parameters({"flags": {"peer": {"requestRelay": True}}})

    for peer in peers:
        rand_delay = round(random.random() *
                           (max_range - min_range) + min_range, 1)
        peer.yearly_message_count = SECONDS_IN_YEAR / rand_delay

        peer.params = params
        peer.running = True

    await asyncio.sleep(exc_time)

    buffer = MessageQueue().buffer

    calls_and_delays = {
        p.address.hopr: {"calls": 0, "delay": await p.message_delay} for p in peers
    }

    while buffer.qsize() > 0:
        calls_and_delays[await buffer.get()]["calls"] += 1

    durations = [
        (values["calls"] + 1) * values["delay"] for values in calls_and_delays.values()
    ]
    assert (max(durations) - min(durations)) < (max_range * 2)
