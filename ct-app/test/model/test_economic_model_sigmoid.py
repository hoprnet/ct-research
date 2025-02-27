import pytest

from core.components.parameters import SigmoidParams
from core.economic_model import Budget


def test_values_mid_range():
    economic_model = SigmoidParams({
        "proportion": 1,
        "max_apr": 20.0,
        "offset": 0,
        "buckets": {
            "network_capacity": {
                "flatness": 1,
                "skewness": 1,
                "upperbound": 1,
                "offset": 0,
            },
            "economic_security": {
                "flatness": 1,
                "skewness": 1,
                "upperbound": 0.5,
                "offset": 0,
            },
        }
    })

    economic_model.offset = 0
    assert economic_model.apr([0.5, 0.25]) == 0

    economic_model.offset = 10
    assert economic_model.apr([0.5, 0.25]) == 10 # fails because the order of buckets is not guaranteed


def test_value_above_mid_range():
    economic_model = SigmoidParams({
        "proportion": 1,
        "max_apr": 20.0,
        "offset": 0,
        "buckets": {
            "network_capacity": {
                "flatness": 1,
                "skewness": 1,
                "upperbound": 1,
                "offset": 0,
            }
        }
    })


    assert economic_model.apr([0.75]) == 0


def test_value_below_mid_range():
    economic_model = SigmoidParams({
        "proportion": 1,
        "max_apr": 20.0,
        "offset": 0,
        "buckets": {
            "network_capacity": {
                "flatness": 1,
                "skewness": 1,
                "upperbound": 1,
                "offset": 0,
            }
        }
    })

    assert economic_model.apr([0.25]) > 0


def test_apr_composition():
    assert EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)], 20.0, 1).apr(
        [0.25]
    ) == EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)] * 2, 20.0, 1).apr(
        [0.25] * 2
    )


def test_out_of_bounds_values():
    assert (
        EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 0.5, 0)], 20.0, 1).apr([0.5])
        == 0
    )

    assert (
        EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 0.5, 0)], 20.0, 1).apr([0]) == 0
    )


def test_bucket_apr():
    bucket = Bucket("bucket", 1, 1, 0.5, 0)

    with pytest.raises(ValueError):
        bucket.apr(0)

    assert bucket.apr(0.125) > 0
    assert bucket.apr(0.25) == 0
    assert bucket.apr(0.375) == 0

    with pytest.raises(ValueError):
        bucket.apr(0.5)


def test_yearly_message_count(budget: Budget):
    stake = 75000
    model = EconomicModelSigmoid(
        10.0,
        [Bucket("bucket_1", 1, 1, 1, 0), Bucket("bucket_2", 1, 1, 0.5, 0)],
        20.0,
        1,
    )
    model.budget = budget

    assert model.apr([0.5, 0.25]) == 10

    assert model.yearly_message_count(stake, [0.5, 0.25]) == round(
        model.apr([0.5, 0.25])
        / 100
        * stake
        / (budget.ticket_price)
    )
