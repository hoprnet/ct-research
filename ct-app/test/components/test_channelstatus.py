from core.components.channelstatus import ChannelStatus


def test_channelstatus():
    assert ChannelStatus.isPending("PendingToClose")
    assert not ChannelStatus.isPending("Open")
    assert not ChannelStatus.isPending("Closed")

    assert not ChannelStatus.isOpen("PendingToClose")
    assert ChannelStatus.isOpen("Open")
    assert not ChannelStatus.isOpen("Closed")

    assert not ChannelStatus.isClosed("PendingToClose")
    assert not ChannelStatus.isClosed("Open")
    assert ChannelStatus.isClosed("Closed")
