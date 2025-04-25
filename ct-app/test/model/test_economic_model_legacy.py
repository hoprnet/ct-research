import pytest

from core.economic_model import (
    Budget,
    Coefficients,
    EconomicModelLegacy,
    Equation,
    Equations,
)


@pytest.fixture
def model(budget: Budget):
    model = EconomicModelLegacy(
        Equations(
            Equation("a * x", "l <= x <= c"),
            Equation("a * c + (x - c) ** (1 / b)", "x > c"),
        ),
        Coefficients(1, 1.4, 75000, 10000),
        1,
        20.0,
    )
    model.budget = budget

    return model


def test_transformed_stake(model: EconomicModelLegacy):
    assert model.transformed_stake(0) == 0
    assert model.transformed_stake(model.coefficients.l) == model.coefficients.l
    assert model.transformed_stake(model.coefficients.c) == model.coefficients.c
    assert model.transformed_stake(model.coefficients.c * 2) < (
        model.coefficients.c * 2
    )


def test_message_count_for_reward(model: EconomicModelLegacy):
    assert model.yearly_message_count(0) == 0, "No reward for 0 stake"

    assert round(
        model.yearly_message_count(model.coefficients.l) / model.coefficients.l, 2
    ) == round(
        model.yearly_message_count(model.coefficients.c) / model.coefficients.c, 2
    ), "Linear result in [l, c] range"

    assert round(
        model.yearly_message_count(model.coefficients.c) / model.coefficients.c, 2
    ) < round(
        2 * model.yearly_message_count(2 * model.coefficients.c) / model.coefficients.c,
        2,
    ), "Non linear above [l, c] range"
