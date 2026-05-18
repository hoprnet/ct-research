import pytest

from core.api.response_objects import Channel
from core.components.utils import Utils


@pytest.fixture
def channel_topology():
    return [
        Channel(
            {
                "balance": "1 wxHOPR",
                "destination": "dst_1",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "2 wxHOPR",
                "destination": "dst_2",
                "source": "src_1",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "3 wxHOPR",
                "destination": "dst_3",
                "source": "src_1",
                "status": "Closed",
            }
        ),
        Channel(
            {
                "balance": "4 wxHOPR",
                "destination": "dst_1",
                "source": "src_2",
                "status": "Open",
            }
        ),
        Channel(
            {
                "balance": "1 wxHOPR",
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
