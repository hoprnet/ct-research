import pytest

from core.api.response_objects import TicketPrice
from core.components.parameters import LegacyParams


@pytest.fixture
def model() -> LegacyParams:
    return LegacyParams({
        "proportion": 1,
        "apr": 20,
        "coefficients": {
            "a": 1,
            "b": 1.4,
            "c": 75000,
            "l": 10000
        },
        "equations": {
            "fx": {
                "formula": "a * x",
                "condition": "l <= x <= c"
            },
            "gx": {
                "formula": "a * c + (x - c) ** (1 / b)",
                "condition": "x > c"
            }
        }
    })


def test_transformed_stake(model: LegacyParams):
    assert model.transformed_stake(0) == 0
    assert model.transformed_stake(
        model.coefficients.l) == model.coefficients.l
    assert model.transformed_stake(
        model.coefficients.c) == model.coefficients.c
    assert model.transformed_stake(model.coefficients.c * 2) < (
        model.coefficients.c * 2
    )


def test_message_count_for_reward(model: LegacyParams):
    ticket_price = TicketPrice({"price": "100000000000000"})

    assert model.yearly_message_count(
        0, ticket_price) == 0, "No reward for 0 stake"

    assert round(
        model.yearly_message_count(
            model.coefficients.l, ticket_price) / model.coefficients.l, 2
    ) == round(
        model.yearly_message_count(
            model.coefficients.c, ticket_price) / model.coefficients.c, 2
    ), "Linear result in [l, c] range"

    assert round(
        model.yearly_message_count(
            model.coefficients.c, ticket_price) / model.coefficients.c, 2
    ) < round(
        2 * model.yearly_message_count(2 * model.coefficients.c,
                                       ticket_price) / model.coefficients.c,
        2,
    ), "Non linear above [l, c] range"
