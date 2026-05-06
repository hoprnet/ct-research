import pytest

from core.types.balance import Balance

from .module.metric import Metric


def test_metric_condition_supports_numeric_comparisons():
    assert Metric("latency", 10, "ms", cdt=">= 10").cdt is True
    assert Metric("latency", 10, "ms", cdt="< 5").cdt is False


def test_metric_condition_supports_balance_comparisons():
    baseline = Metric("Initial balance", Balance("1 wxHOPR"))
    current = Metric("Final balance", Balance("2 wxHOPR"), cdt=f"!= {baseline.v}")

    assert current.cdt is True


def test_metric_condition_rejects_unsupported_operator():
    metric = Metric("latency", 10, "ms", cdt="<> 5")

    with pytest.raises(ValueError, match="Unsupported metric condition"):
        _ = metric.cdt
