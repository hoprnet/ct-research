from core.components.channelstatus import ChannelStatus


def test_channelstatus():
    assert ChannelStatus.isPending("PendingToClose")
    assert not ChannelStatus.isPending("Open")
    assert not ChannelStatus.isOpen("PendingToClose")
    assert ChannelStatus.isOpen("Open")
