from core.model.peer import Peer
from packaging.version import Version


def test_peer_version():
    peer = Peer("some_id", "some_address", "0.0.1")

    peer.version = "0.1.0-rc.1"
    assert peer.version_is_old("0.1.0-rc.2")
    assert peer.version_is_old(Version("0.1.0-rc.2"))

    peer.version = "0.1.0-rc.1"
    assert not peer.version_is_old("0.1.0-rc.0")
    assert not peer.version_is_old(Version("0.1.0-rc.0"))

    peer.version = "0.1.1"
    assert not peer.version_is_old("0.1.0-rc.3")
    assert not peer.version_is_old(Version("0.1.0-rc.3"))

    peer.version = "0.1.0-rc.1"
    assert not peer.version_is_old("0.1.0-rc.1")
    assert not peer.version_is_old(Version("0.1.0-rc.1"))

    peer.version = "2.0"
    assert not peer.version_is_old("2.0")
    assert not peer.version_is_old(Version("2.0"))

    peer.version = "2.0"
    assert peer.version_is_old("2.1")
    assert peer.version_is_old(Version("2.1"))

    peer.version = "2.0.7"
    assert not peer.version_is_old("2.0.7")
    assert not peer.version_is_old(Version("2.0.7"))
