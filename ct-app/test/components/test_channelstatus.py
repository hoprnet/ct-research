from core.api.channelstatus import ChannelStatus


def test_channelstatus():
    open_status = ChannelStatus.fromString("Open")
    close_status = ChannelStatus.fromString("Closed")
    pending_status = ChannelStatus.fromString("PendingToClose")
    unknown_status = ChannelStatus.fromString("Unknown")

    assert open_status.isOpen
    assert not close_status.isOpen
    assert not pending_status.isOpen

    assert not open_status.isClosed
    assert close_status.isClosed
    assert not pending_status.isClosed

    assert not open_status.isPending
    assert not close_status.isPending
    assert pending_status.isPending

    assert unknown_status is None
