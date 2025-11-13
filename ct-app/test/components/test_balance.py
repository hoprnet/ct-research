from decimal import Decimal

import pytest

from core.components.balance import WEI_TO_READABLE, Balance


def test_read_balance():
    assert Balance("42.314 wxHOPR").value == Decimal("42.314")
    assert Balance("42.314 wxHOPR").unit == "wxHOPR"

    assert Balance("42.314 wei wxHOPR").value == Decimal("42.314") / WEI_TO_READABLE
    assert Balance("42.314 wei wxHOPR").unit == "wxHOPR"

    with pytest.raises(TypeError):
        Balance(42.314)  # ty: ignore[invalid-argument-type]

    with pytest.raises(TypeError):
        Balance("42.314")

    with pytest.raises(TypeError):
        Balance("42.314 sub wei wxHOPR")

    with pytest.raises(TypeError):
        Balance("Not_A_Decimal wxHOPR")


def test_from_float():
    assert Balance.from_float(42.314, "wxHOPR").value == Decimal("42.314")
    assert Balance.from_float(42.314, "wxHOPR").unit == "wxHOPR"

    assert Balance.from_float(42.314, "wei wxHOPR").value == Decimal("42.314") / WEI_TO_READABLE
    assert Balance.from_float(42.314, "wei wxHOPR").unit == "wxHOPR"


def test_comparison():
    assert Balance("1.1 unit") < Balance("1.2 unit")
    assert Balance("1.1 unit") < Balance("1200000000000000000 wei unit")
    assert Balance("1.1 unit") == Balance("1100000000000000000 wei unit")

    assert Balance("1200000000000000000 wei unit") > Balance("1.1 unit")


def test_failing_comparison():
    with pytest.raises(TypeError):
        Balance("1.0 unit") < 10

    with pytest.raises(ValueError):
        Balance("1.0 unit") < Balance("2.0 _unit")


def test_addition():
    assert Balance("1.0 unit") + Balance("2.1 unit") == Balance("3.1 unit")


def test_substraction():
    assert Balance("2.1 unit") - Balance("1.0 unit") == Balance("1.1 unit")

    with pytest.raises(TypeError):
        Balance("2.1 unit") - Balance("1.0 _unit")


def test_div():
    # div
    assert Balance("2.1 unit") / 2.0 == Balance("1.05 unit")
    assert Balance("2.1 unit") / Decimal("2.0") == Balance("1.05 unit")
    assert Balance("10 unit") / Balance("5 unit") == 2

    with pytest.raises(TypeError):
        Balance("2.1 unit") / Balance("2.0 _unit")

    # rdiv
    assert (2.1 / Balance("2.0 unit")) == Balance("1.05 unit")
    assert Decimal("2.1") / Balance("2.0 unit") == Balance("1.05 unit")


def test_mul():
    # mul
    assert Balance("2.1 unit") * 2.0 == Balance("4.2 unit")
    assert Balance("2.1 unit") * Decimal("2.0") == Balance("4.2 unit")

    with pytest.raises(TypeError):
        Balance("2.1 unit") * Balance("2.0 unit")

    # rmul
    assert 2.0 * Balance("2.1 unit") == Balance("4.2 unit")


def test_power():
    assert Balance("2.0 unit") ** 2 == Balance("4 unit")
    assert Balance("2.0 unit") ** 2.0 == Balance("4 unit")
    assert Balance("2.1 unit") ** Decimal("2") == Balance("4.41 unit")

    with pytest.raises(TypeError):
        Balance("2.1 unit") ** Balance("2.0 unit")


def test_round():
    assert round(Balance("2.12 unit"), 1) == Balance("2.1 unit")
    assert round(Balance("2.126 unit"), 2) == Balance("2.13 unit")
