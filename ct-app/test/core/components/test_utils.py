import pytest

from core.api.response_objects import Channel
from core.components.utils import Utils


@pytest.fixture
def channel_topology():
    return [
        Channel(
            {
                "balance": "1 wxHOPR",
                "channelId": "channel_1",
                "destination": "dst_1",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "2 wxHOPR",
                "channelId": "channel_2",
                "destination": "dst_2",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "3 wxHOPR",
                "channelId": "channel_3",
                "destination": "dst_3",
                "source": "src_1",
                "status": "Closed",
            }
        ),
        Channel(
            {
                "balance": "4 wxHOPR",
                "channelId": "channel_4",
                "destination": "dst_1",
                "source": "src_2",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "1 wxHOPR",
                "channelId": "channel_5",
                "destination": "dst_2",
                "source": "src_2",
                "status": "Open",
            }
        ),
    ]


@pytest.mark.asyncio
async def test_balanceInChannels(channel_topology):
    results = await Utils.balanceInChannels(channel_topology)
    assert len(results) == 2
    assert results["src_1"].value == 3
    assert results["src_2"].value == 5
