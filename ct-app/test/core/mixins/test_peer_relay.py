from types import SimpleNamespace
from typing import Any, cast

import pytest

from core.mixins.peer_relay import PeerRelayMixin
from core.services.relay_pacer import RelayPacer
from core.types.message_format import MessageFormat
from core.types.message_queue import MessageQueue


class FakePeer:
    def __init__(self, address: str, delay: float, yearly_message_count: float | None = 1.0):
        self.address = SimpleNamespace(native=address)
        self._delay = delay
        self.yearly_message_count = yearly_message_count

    @property
    def message_delay(self) -> float | None:
        if self.yearly_message_count is None:
            return None
        return self._delay

    def build_relay_request(
        self,
        delay: float,
        minimum_delay_between_batches: float,
    ) -> MessageFormat:
        return MessageFormat(self.address.native, batch_size=3)


class DummyRelayNode(PeerRelayMixin):
    pass


def _drain_queue() -> None:
    queue = MessageQueue().buffer
    while not queue.empty():
        queue.get_nowait()


@pytest.mark.asyncio
async def test_relay_messages_uses_per_peer_pacing(mocker):
    _drain_queue()
    node = DummyRelayNode()
    node.peers = cast(
        dict[str, Any],
        {
            "peer_fast": FakePeer("peer_fast", delay=1.0),
            "peer_slow": FakePeer("peer_slow", delay=2.0),
        },
    )
    node.relay_pacer = RelayPacer()
    node.params = cast(
        Any,
        SimpleNamespace(
            peer=SimpleNamespace(minimum_delay_between_batches=SimpleNamespace(value=2.0))
        ),
    )

    monotonic = mocker.patch("core.mixins.peer_relay.time.monotonic", return_value=100.0)

    await node._relay_messages_once()
    queue = MessageQueue().buffer
    assert queue.qsize() == 2

    monotonic.return_value = 103.5
    await node._relay_messages_once()
    assert queue.qsize() == 3

    relayers = []
    while not queue.empty():
        relayers.append(queue.get_nowait().relayer)

    assert relayers.count("peer_fast") == 2
    assert relayers.count("peer_slow") == 1


@pytest.mark.asyncio
async def test_relay_messages_cleans_stale_relayer_state(mocker):
    _drain_queue()
    node = DummyRelayNode()
    node.peers = cast(dict[str, Any], {"peer_a": FakePeer("peer_a", delay=1.0)})
    node.relay_pacer = RelayPacer()
    node.relay_pacer._last_sent_at["peer_removed"] = 200.0
    node.params = cast(
        Any,
        SimpleNamespace(
            peer=SimpleNamespace(minimum_delay_between_batches=SimpleNamespace(value=2.0))
        ),
    )

    mocker.patch("core.mixins.peer_relay.time.monotonic", return_value=100.0)

    await node._relay_messages_once()

    assert "peer_removed" not in node.relay_pacer._last_sent_at
    assert "peer_a" in node.relay_pacer._last_sent_at
