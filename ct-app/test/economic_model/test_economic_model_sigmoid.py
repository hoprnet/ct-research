from copy import deepcopy

import pytest

from core.api.response_objects import TicketPrice
from core.components.parameters import BucketParams, SigmoidParams


def test_values_mid_range():
    model = SigmoidParams(
        {
            "proportion": 1,
            "max_apr": 20.0,
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
            },
        }
    )

    model.offset = 0
    assert model.apr([0.5, 0.25]) == 0

    model.offset = 10.0
    assert model.apr([0.5, 0.25]) == 10


def test_value_above_mid_range():
    model = SigmoidParams(
        {
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
            },
        }
    )

    assert model.apr([0.75]) == 0


def test_value_below_mid_range():
    model = SigmoidParams(
        {
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
            },
        }
    )

    assert model.apr([0.25]) > 0


def test_apr_composition():
    model_a = SigmoidParams(
        {
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
            },
        }
    )

    model_b = deepcopy(model_a)
    model_b.buckets.economic_security = BucketParams(
        {
            "flatness": 1,
            "skewness": 1,
            "upperbound": 1,
            "offset": 0,
        }
    )

    assert model_a.apr([0.25]) == model_b.apr([0.25, 0.25])


def test_out_of_bounds_values():
    model = SigmoidParams(
        {
            "proportion": 1,
            "max_apr": 20.0,
            "offset": 0,
            "buckets": {
                "network_capacity": {
                    "flatness": 1,
                    "skewness": 1,
                    "upperbound": 0.5,
                    "offset": 0,
                }
            },
        }
    )

    assert model.apr([0.5]) == 0
    assert model.apr([0]) == 0


def test_bucket_apr():
    bucket = BucketParams(
        {
            "flatness": 1,
            "skewness": 1,
            "upperbound": 0.5,
            "offset": 0,
        }
    )

    with pytest.raises(ValueError):
        bucket.apr(0)

    assert bucket.apr(0.125) > 0
    assert bucket.apr(0.25) == 0
    assert bucket.apr(0.375) == 0

    with pytest.raises(ValueError):
        bucket.apr(0.5)


def test_yearly_message_count():
    stake = 75000
    ticket_price = TicketPrice({"price": "100000000000000"})

    model = SigmoidParams(
        {
            "proportion": 1,
            "max_apr": 20.0,
            "offset": 10.0,
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
            },
        }
    )

    assert model.apr([0.5, 0.25]) == 10

    assert model.yearly_message_count(stake, ticket_price, [0.5, 0.25]) == round(
        model.apr([0.5, 0.25]) / 100 * stake / (ticket_price.value)
    )
