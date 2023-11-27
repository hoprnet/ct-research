from core.model.peer import Peer


def test_peer_version():
    peer = Peer("some_id", "some_address", None)

    peer.version = "v0.1.0-rc.1"
    assert peer.version_is_old("v0.1.0-rc.2")

    peer.version = "v0.1.0-rc.1"
    assert not peer.version_is_old("v0.1.0-rc.0")

    peer.version = "v0.1.1"
    assert not peer.version_is_old("v0.1.0-rc.3")

    peer.version = "v0.1.0-rc.1"
    assert not peer.version_is_old("v0.1.0-rc.1")

    peer.version = "v2.0"
    assert not peer.version_is_old("v2.0")
