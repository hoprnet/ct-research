import random

from core.types.balance import Balance
from core.types.peer import Peer

SECONDS_IN_YEAR = 365 * 24 * 60 * 60


def test_effective_stake_uses_allocated_balance():
    peer = Peer("0xabc")
    peer.channel_balance = Balance("1 wxHOPR")
    peer.yearly_message_count = 10
    peer.set_allocation("0xsafe", Balance("9 wxHOPR"), 3)

    assert peer.effective_stake == Balance("3 wxHOPR")


def test_effective_stake_falls_back_to_channel_balance_without_allocation():
    peer = Peer("0xabc")
    peer.channel_balance = Balance("2 wxHOPR")
    peer.yearly_message_count = 10

    assert peer.effective_stake == Balance("2 wxHOPR")


def test_is_eligible_rejects_missing_safe_or_excluded_peer():
    peer = Peer("0xabc")
    assert peer.is_eligible(Balance.zero("wxHOPR"), [], []) is False

    peer.set_allocation("0xsafe", Balance("3 wxHOPR"), 1)
    assert peer.is_eligible(Balance.zero("wxHOPR"), [], ["0xabc"]) is False


def test_message_delay_returns_none_for_zero_message_count():
    peer = Peer("0xabc")
    peer.yearly_message_count = 0
    assert peer.message_delay is None


def test_build_relay_request_computes_batch_size():
    peer = Peer("0xabc")
    message = peer.build_relay_request(delay=1.0, minimum_delay_between_batches=2.0)
    assert message.relayer == "0xabc"
    assert message.batch_size >= 3


def test_next_idle_sleep_uses_normal_distribution(monkeypatch):
    peer = Peer("0xabc")
    monkeypatch.setattr(random, "normalvariate", lambda mean, std: 8.5)
    assert peer.next_idle_sleep(7.0, 1.5) == 8.5


def test_message_delay_formula():
    peer = Peer("0xabc")
    peer.yearly_message_count = SECONDS_IN_YEAR
    assert peer.message_delay == 2.0
