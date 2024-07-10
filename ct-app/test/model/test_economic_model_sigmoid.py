import pytest
from core.components.parameters import Parameters
from core.model.budget import Budget
from core.model.economic_model_sigmoid import Bucket, EconomicModelSigmoid


def test_init_class():
    config = {
        "sigmoid": {
            "proportion": 0.1,
            "maxAPR": 15.0,
            "offset": 10.0,
            "buckets": {
                "bucket_1": {
                    "flatness": 1,
                    "skewness": 2,
                    "upperbound": 3,
                },
                "bucket_2": {
                    "flatness": 4,
                    "skewness": 5,
                    "upperbound": 6,
                },
            },
        }
    }
    params = Parameters()
    params.parse(config)

    economic_model = EconomicModelSigmoid.fromParameters(params.sigmoid)
    bucket = economic_model.buckets[0]

    assert len(economic_model.buckets) == len(config["sigmoid"]["buckets"])

    for bucket in economic_model.buckets:
        assert bucket.flatness == config["sigmoid"]["buckets"][bucket.name]["flatness"]
        assert bucket.skewness == config["sigmoid"]["buckets"][bucket.name]["skewness"]
        assert (
            bucket.upperbound == config["sigmoid"]["buckets"][bucket.name]["upperbound"]
        )


def test_values_mid_range():
    assert (
        EconomicModelSigmoid(
            0, [Bucket("bucket_1", 1, 1, 1), Bucket("bucket_2", 1, 1, 0.5)], 20.0, 1
        ).apr([0.5, 0.25])
        == 0
    )

    assert (
        EconomicModelSigmoid(
            10.0, [Bucket("bucket_1", 1, 1, 1), Bucket("bucket_2", 1, 1, 0.5)], 20.0, 1
        ).apr([0.5, 0.25])
        == 10
    )


def test_value_above_mid_range():
    assert EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)], 20.0, 1).apr([0.75]) < 0


def test_value_below_mid_range():
    assert EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)], 20.0, 1).apr([0.25]) > 0


def test_apr_composition():
    assert EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)], 20.0, 1).apr(
        [0.25]
    ) * 2 == EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)] * 2, 20.0, 1).apr(
        [0.25] * 2
    )

    assert EconomicModelSigmoid(1, [Bucket("bucket", 1, 1, 1)], 20.0, 1).apr(
        [0.25]
    ) * 2 != EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 1)] * 2, 20.0, 1).apr(
        [0.25] * 2
    )


def test_out_of_bounds_values():
    with pytest.raises(ValueError):
        EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 0.5)], 20.0, 1).apr([0.5])

    with pytest.raises(ValueError):
        EconomicModelSigmoid(0, [Bucket("bucket", 1, 1, 0.5)], 20.0, 1).apr([0])


def test_bucket_apr():
    bucket = Bucket("bucket", 1, 1, 0.5)

    with pytest.raises(ValueError):
        bucket.apr(0)

    assert bucket.apr(0.125) > 0
    assert bucket.apr(0.25) == 0
    assert bucket.apr(0.375) < 0

    with pytest.raises(ValueError):
        bucket.apr(0.5)


def test_yearly_message_count(budget: Budget):
    stake = 75000
    model = EconomicModelSigmoid(
        10.0, [Bucket("bucket_1", 1, 1, 1), Bucket("bucket_2", 1, 1, 0.5)], 20.0, 1
    )
    model.budget = budget

    assert model.apr([0.5, 0.25]) == 10
    assert model.yearly_message_count(stake, [0.5, 0.25]) == round(
        model.apr([0.5, 0.25])
        * stake
        / 100.0
        / (budget.ticket_price * budget.winning_probability)
    )
