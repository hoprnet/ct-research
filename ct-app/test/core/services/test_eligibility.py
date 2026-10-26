from core.api.response_objects import Channel
from core.services.eligibility import is_eligible, qualifying_outgoing_channels
from core.types.balance import Balance


def _channel(source: str, balance: str, status: str = "Open") -> Channel:
    return Channel(
        {"balance": balance, "source": source, "destination": "0xdest", "status": status}
    )


def test_qualifying_channels_ignore_small_and_non_open_channels():
    channels = [
        _channel("0xa", "50 wxHOPR"),
        _channel("0xa", "60 wxHOPR"),
        _channel("0xa", "49.9 wxHOPR"),
        _channel("0xa", "100 wxHOPR", status="PendingToClose"),
        _channel("0xb", "50 wxHOPR"),
    ]

    counts = qualifying_outgoing_channels(channels, Balance("50 wxHOPR"))

    assert counts == {"0xa": 2, "0xb": 1}


def test_is_eligible_requires_reachability_and_enough_channels():
    assert is_eligible("0xa", True, 5, 5, [], []) is True
    assert is_eligible("0xa", True, 4, 5, [], []) is False
    assert is_eligible("0xa", False, 10, 5, [], []) is False


def test_is_eligible_rejects_ct_nodes_and_excluded_peers():
    assert is_eligible("0xa", True, 10, 5, ["0xa"], []) is False
    assert is_eligible("0xa", True, 10, 5, [], ["0xa"]) is False
