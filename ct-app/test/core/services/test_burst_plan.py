from datetime import datetime, timezone

import pytest

from core.config_parser.incentive import IncentiveParams
from core.services.burst_plan import (
    RelayedCostTracker,
    RoundPlan,
    packet_rate,
    packets_per_burst,
    send_rate,
)
from core.types.balance import Balance

TICKET_PRICE = Balance("0.00001 wxHOPR")


def _params(**overrides) -> IncentiveParams:
    values = {
        "min_outgoing_channels": 5,
        "min_channel_balance": "50 wxHOPR",
        "burst_rate": 8,
        "burst_duration": "10s",
        "target_relayer_interval": "600s",
        "max_concurrent_bursts_per_ct": 0,
        "ct_node_count": 5,
    }
    values.update(overrides)
    return IncentiveParams(values)


def test_packet_rate_counts_the_whole_mtu():
    assert packet_rate(8, 1024) == pytest.approx(976.5625)
    # A larger MTU means fewer packets for the same bit rate.
    assert packet_rate(8, 2048) == pytest.approx(488.28125)


def test_ct_node_sends_half_of_what_the_relayer_is_paid_for():
    # Each packet crosses the relayer out and back, so it is relayed (and ticketed) twice.
    assert send_rate(8, 1024) == pytest.approx(488.28125)
    assert packets_per_burst(8, 10, 1024) == 4883


def test_round_plan_at_300_relayers_matches_protocol_reference():
    plan = RoundPlan.build(_params(), 300)

    assert plan.round_duration == 3000
    assert plan.step == 10
    assert plan.concurrency == 1
    assert plan.peak_concurrency == 1
    assert plan.relayer_interval == 600
    assert plan.avg_outbound_mbps == 4
    assert plan.bursts_per_relayer_per_month == 4320
    assert plan.packets_per_relayer_per_month(1024) == pytest.approx(42_187_500)
    assert plan.max_reward_per_relayer_month(1024, TICKET_PRICE) == Balance("421.875 wxHOPR")
    assert plan.max_monthly_cost(1024, TICKET_PRICE) == Balance("126562.5 wxHOPR")


@pytest.mark.parametrize(
    "relayers, concurrency, peak",
    [(50, 1 / 6, 1), (300, 1, 1), (500, 5 / 3, 2), (600, 2, 2), (1000, 10 / 3, 4)],
)
def test_round_length_does_not_depend_on_network_size(relayers, concurrency, peak):
    plan = RoundPlan.build(_params(), relayers)

    assert plan.round_duration == 3000
    assert plan.relayer_interval == 600
    assert plan.concurrency == pytest.approx(concurrency)
    assert plan.peak_concurrency == peak
    assert plan.capped is False


def test_concurrency_cap_stretches_the_round():
    plan = RoundPlan.build(_params(max_concurrent_bursts_per_ct=2), 1000)

    assert plan.capped is True
    assert plan.round_duration == pytest.approx(5000)
    assert plan.concurrency == pytest.approx(2)
    assert plan.relayer_interval == pytest.approx(1000)
    # Cost stops growing at N = m x N_1: 2 x 126,562.5 wxHOPR.
    assert plan.max_monthly_cost(1024, TICKET_PRICE) == Balance("253125 wxHOPR")


def test_concurrency_cap_is_ignored_when_not_reached():
    plan = RoundPlan.build(_params(max_concurrent_bursts_per_ct=2), 600)

    assert plan.capped is False
    assert plan.round_duration == 3000


def test_round_length_scales_with_ct_node_count():
    plan = RoundPlan.build(_params(ct_node_count=2), 300)

    assert plan.round_duration == 1200
    assert plan.relayer_interval == 600


@pytest.mark.parametrize(
    "overrides",
    [
        {"ct_node_count": 0},
        {"burst_duration": "0s"},
        {"target_relayer_interval": "0s"},
        {"burst_rate": 0},
    ],
)
def test_round_plan_rejects_invalid_parameters(overrides):
    with pytest.raises(ValueError):
        RoundPlan.build(_params(**overrides), 10)


def test_round_plan_rejects_empty_round():
    with pytest.raises(ValueError):
        RoundPlan.build(_params(), 0)


def test_summary_includes_cost_only_with_mtu_and_ticket_price():
    plan = RoundPlan.build(_params(), 300)

    assert "packets_per_burst" not in plan.summary()
    assert "projected_max_monthly_cost" not in plan.summary(1024)

    summary = plan.summary(1024, TICKET_PRICE)
    assert summary["packets_per_burst"] == 4883
    assert summary["projected_max_monthly_cost"] == "126562.5000 wxHOPR"


def test_cost_tracker_counts_two_tickets_per_echo_and_resets_each_month():
    tracker = RelayedCostTracker()
    september = datetime(2026, 9, 29, tzinfo=timezone.utc)
    october = datetime(2026, 10, 1, tzinfo=timezone.utc)

    assert tracker.add(100, 80, TICKET_PRICE, september) == Balance("0.0016 wxHOPR")
    tracker.add(100, 20, TICKET_PRICE, september)
    assert tracker.packets_echoed == 100
    assert tracker.cost == Balance("0.002 wxHOPR")

    tracker.add(10, 10, TICKET_PRICE, october)
    assert tracker.packets_sent == 10
    assert tracker.cost == Balance("0.0002 wxHOPR")


def test_cost_tracker_counts_packets_without_ticket_price():
    tracker = RelayedCostTracker()

    assert tracker.add(10, 5, None) is None
    assert tracker.packets_echoed == 5
    assert tracker.summary()["month_to_date_cost"] is None
