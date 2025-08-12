from copy import deepcopy
from decimal import Decimal

import pytest

from core.api.response_objects import TicketPrice
from core.components.balance import Balance
from core.components.config_parser.economic_model import BucketParams, SigmoidParams


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

    model.offset = Decimal(0)
    assert model.apr([Decimal("0.5"), Decimal("0.25")]) == 0

    model.offset = Decimal(10)
    assert model.apr([Decimal("0.5"), Decimal("0.25")]) == 10


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

    assert model.apr([Decimal("0.75")]) == 0


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

    assert model.apr([Decimal("0.25")]) > 0


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

    assert model_a.apr([Decimal("0.25")]) == model_b.apr([Decimal("0.25"), Decimal("0.25")])


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

    assert model.apr([Decimal("0.5")]) == 0
    assert model.apr([Decimal("0")]) == 0


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
        bucket.apr(Decimal(0))

    assert bucket.apr(Decimal("0.125")) > 0
    assert bucket.apr(Decimal("0.25")) == 0
    assert bucket.apr(Decimal("0.375")) == 0

    with pytest.raises(ValueError):
        bucket.apr(Decimal("0.5"))


def test_yearly_message_count():
    stake = Balance("75000 wxHOPR")
    ticket_price = TicketPrice({"price": "00001 wxHOPR"})

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

    assert model.apr([Decimal("0.5"), Decimal("0.25")]) == 10

    assert model.yearly_message_count(
        stake, ticket_price, [Decimal("0.5"), Decimal("0.25")]
    ) == round(model.apr([Decimal("0.5"), Decimal("0.25")]) / 100 * stake / (ticket_price.value))
