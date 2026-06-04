from types import SimpleNamespace
from typing import Any, cast

from core.services.relay_pacer import RelayPacer
from core.types.message_format import MessageFormat


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


def test_due_messages_respects_per_peer_next_send_at():
    pacer = RelayPacer()
    peers = {
        "peer_fast": FakePeer("peer_fast", delay=1.0),
        "peer_slow": FakePeer("peer_slow", delay=2.0),
    }

    first, first_next_due = pacer.due_messages(
        cast(dict[str, Any], peers), minimum_delay_between_batches=2.0, now=100.0
    )
    second, second_next_due = pacer.due_messages(
        cast(dict[str, Any], peers), minimum_delay_between_batches=2.0, now=103.5
    )

    assert sorted(message.relayer for message in first) == ["peer_fast", "peer_slow"]
    assert [message.relayer for message in second] == ["peer_fast"]
    assert first_next_due is None
    assert second_next_due == 2.5


def test_due_messages_prunes_stale_relayers():
    pacer = RelayPacer()
    pacer._last_sent_at["removed"] = 999.0
    peers = {"peer_a": FakePeer("peer_a", delay=1.0)}

    pacer.due_messages(cast(dict[str, Any], peers), minimum_delay_between_batches=2.0, now=100.0)

    assert "removed" not in pacer._last_sent_at
    assert "peer_a" in pacer._last_sent_at


def test_due_messages_applies_updated_rate_for_existing_peer():
    pacer = RelayPacer()
    peer = FakePeer("peer_a", delay=2.0)
    peers = {"peer_a": peer}

    first, first_next_due = pacer.due_messages(
        cast(dict[str, Any], peers), minimum_delay_between_batches=2.0, now=100.0
    )
    assert [message.relayer for message in first] == ["peer_a"]
    assert first_next_due is None

    peer._delay = 1.0
    second, second_next_due = pacer.due_messages(
        cast(dict[str, Any], peers), minimum_delay_between_batches=2.0, now=103.5
    )
    assert [message.relayer for message in second] == ["peer_a"]
    assert second_next_due is None
