import time
import pytest
from netwatcher.peer import Peer
from netwatcher.address import Address


@pytest.fixture
def peer():
    return Peer(Address("some_peer", "some_address"))


def test_timestamp_set_on_latency_set(peer: Peer):
    peer.latency = 10

    assert peer.timestamp is not None


def test_transmit_set_on_timestamp_set(peer: Peer):
    peer.latency = 10

    assert peer.timestamp is not None
    assert peer.transmit is True


def test_transmit_not_set_on_latency_set_to_none(peer: Peer):
    peer.latency = None

    assert peer.timestamp is None
    assert peer.transmit is False


def test_transmit_set_on_latency_set_to_minus_one(peer: Peer):
    peer.latency = -1

    assert peer.timestamp is not None
    assert peer.transmit is True


def test_close_channel_not_set_on_timestamp_set_to_none(peer: Peer):
    peer.timestamp = None

    assert peer.close_channel is False


def test_close_channel_not_set_on_timestamp_set_to_now(peer: Peer):
    peer.timestamp = 0

    assert peer.close_channel is False


def test_close_channel_set_on_timestamp_set_to_24_hours_ago(peer: Peer):
    peer.timestamp = time.time() - 60 * 60 * 24 - 1

    assert peer.close_channel is True
