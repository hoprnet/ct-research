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
            "coefficients": {
                "a": 1,
                "b": 1.4,
                "upperbound": "75000 wxHOPR",
                "lowerbound": "10000 wxHOPR",
            },
            "equations": {
                "fx": {"formula": "a * x", "condition": "lowerbound <= x <= upperbound"},
                "gx": {
                    "formula": "a * upperbound + (x - upperbound) ** (1 / b)",
                    "condition": "x > upperbound",
                },
            },
        }
    )


def test_transformed_stake(model: LegacyParams):
    assert model.transformed_stake(ZERO_BALANCE) == ZERO_BALANCE
    assert model.transformed_stake(model.coefficients.lowerbound) == model.coefficients.lowerbound
    assert model.transformed_stake(model.coefficients.upperbound) == model.coefficients.upperbound
    assert model.transformed_stake(model.coefficients.upperbound * 2) < (
        model.coefficients.upperbound * 2
    )


def test_message_count_for_reward(model: LegacyParams):
    ticket_price = TicketPrice({"price": "0.0001 wxHOPR"})

    assert model.yearly_message_count(ZERO_BALANCE, ticket_price) == 0, "No reward for 0 stake"

    assert round(
        model.yearly_message_count(model.coefficients.lowerbound, ticket_price)
        / model.coefficients.lowerbound,
        2,
    ) == round(
        model.yearly_message_count(model.coefficients.upperbound, ticket_price)
        / model.coefficients.upperbound,
        2,
    ), "Linear result in [lowerbound, upperbound] range"

    assert round(
        model.yearly_message_count(model.coefficients.upperbound, ticket_price)
        / model.coefficients.upperbound,
        2,
    ) < round(
        2
        * model.yearly_message_count(2 * model.coefficients.upperbound, ticket_price)
        / model.coefficients.upperbound,
        2,
    ), "Non linear above [lowerbound, upperbound] range"
