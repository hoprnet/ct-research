import pytest
from core.model.budget import Budget
from core.model.economic_model_legacy import (
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
        Coefficients(1, 2, 3, 1),
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
    assert model.message_count_for_reward(0) == 0, "No reward for 0 stake"
    assert model.message_count_for_reward(model.coefficients.l) == round(
        model.coefficients.l * model.apr / model.budget.ticket_price / 12
    ), "Linear result if stake is minimum"
    assert model.message_count_for_reward(model.coefficients.c) == round(
        model.coefficients.c * model.apr / model.budget.ticket_price / 12
    ), "Linear result if stake is at threshold"
    assert model.message_count_for_reward(model.coefficients.c * 2) < round(
        (model.coefficients.c * 2) * model.apr / model.budget.ticket_price / 12
    ), "Non-linear result if stake is above threshold"
