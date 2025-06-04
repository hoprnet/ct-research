import pytest

from core.api.response_objects import TicketPrice
from core.components.balance import Balance
from core.components.config_parser.economic_model import LegacyParams

ZERO_BALANCE = Balance.zero("wxHOPR")


@pytest.fixture
def model() -> LegacyParams:
    return LegacyParams(
        {
            "proportion": 1,
            "apr": 20,
            "coefficients": {"a": 1, "b": 1.4, "c": "75000 wxHOPR", "l": "10000 wxHOPR"},
            "equations": {
                "fx": {"formula": "a * x", "condition": "l <= x <= c"},
                "gx": {"formula": "a * c + (x - c) ** (1 / b)", "condition": "x > c"},
            },
        }
    )


def test_transformed_stake(model: LegacyParams):
    assert model.transformed_stake(ZERO_BALANCE) == ZERO_BALANCE
    assert model.transformed_stake(model.coefficients.l) == model.coefficients.l
    assert model.transformed_stake(model.coefficients.c) == model.coefficients.c
    assert model.transformed_stake(model.coefficients.c * 2) < (model.coefficients.c * 2)


def test_message_count_for_reward(model: LegacyParams):
    ticket_price = TicketPrice({"price": "0.0001 wxHOPR"})

    assert model.yearly_message_count(ZERO_BALANCE, ticket_price) == 0, "No reward for 0 stake"

    assert round(
        model.yearly_message_count(model.coefficients.l, ticket_price) / model.coefficients.l,
        2,
    ) == round(
        model.yearly_message_count(model.coefficients.c, ticket_price) / model.coefficients.c,
        2,
    ), "Linear result in [l, c] range"

    assert round(
        model.yearly_message_count(model.coefficients.c, ticket_price) / model.coefficients.c,
        2,
    ) < round(
        2
        * model.yearly_message_count(2 * model.coefficients.c, ticket_price)
        / model.coefficients.c,
        2,
    ), "Non linear above [l, c] range"
