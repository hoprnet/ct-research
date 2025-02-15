from core.api.channelstatus import ChannelStatus


def test_channelstatus():
    open_status = ChannelStatus.fromString("Open")
    close_status = ChannelStatus.fromString("Closed")
    pending_status = ChannelStatus.fromString("PendingToClose")
    unknown_status = ChannelStatus.fromString("Unknown")

    assert open_status.is_open
    assert not close_status.is_open
    assert not pending_status.is_open

    assert not open_status.is_closed
    assert close_status.is_closed
    assert not pending_status.is_closed

    assert not open_status.is_pending
    assert not close_status.is_pending
    assert pending_status.is_pending

    assert unknown_status is None
