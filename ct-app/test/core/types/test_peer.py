from core.types.balance import Balance
from core.types.peer import Peer


def test_new_peer_is_reachable_without_qualifying_channels():
    peer = Peer("0xABC")

    assert peer.address.native == "0xabc"
    assert peer.reachable is True
    assert peer.qualifying_channels == 0
    assert peer.channel_balance is None


def test_peer_tracks_channel_data():
    peer = Peer("0xabc")
    peer.channel_balance = Balance("2 wxHOPR")
    peer.qualifying_channels = 6

    assert peer.channel_balance == Balance("2 wxHOPR")
    assert peer.qualifying_channels == 6


def test_peers_compare_by_address():
    assert Peer("0xabc") == Peer("0xABC")
    assert Peer("0xabc") == "0xabc"
    assert len({Peer("0xabc"), Peer("0xABC")}) == 1
