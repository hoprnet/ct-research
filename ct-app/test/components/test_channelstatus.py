from core.components.channelstatus import ChannelStatus


def test_channelstatus():
    assert ChannelStatus.isOpen("Open")
    assert not ChannelStatus.isOpen("PendingToClose")
    assert not ChannelStatus.isOpen("Closed")

    assert not ChannelStatus.isPending("Open")
    assert ChannelStatus.isPending("PendingToClose")
    assert not ChannelStatus.isPending("Closed")

    assert not ChannelStatus.isClosed("Open")
    assert not ChannelStatus.isClosed("PendingToClose")
    assert ChannelStatus.isClosed("Closed")
