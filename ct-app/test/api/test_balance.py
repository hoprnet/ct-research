from decimal import Decimal

import pytest

from core.components.balance import Balance


def test_parse_string_to_balance():
    balance_str = "100.00 wxHOPR"
    balance = Balance(balance_str)

    assert balance.value == 100.00
    assert balance.unit == "wxHOPR"


def test_parse_string_to_balance_invalid_format():
    balance_str = "100.00 wei wxHOPR but not valid"

    with pytest.raises(TypeError):
        _ = Balance(balance_str)


def test_parse_string_to_balance_empty():
    balance_str = ""

    with pytest.raises(TypeError):
        Balance(balance_str)


def test_compare_balances():
    balance1 = Balance("100.00 wxHOPR")
    balance2 = Balance("100.00 wxHOPR")
    balance3 = Balance("50.00 wxHOPR")

    assert balance1 == balance2
    assert balance1 != balance3
    assert balance1 > balance3
    assert not (balance1 < balance3)


def test_add_balances():
    balance1 = Balance("100.00 wxHOPR")
    balance2 = Balance("50.00 wxHOPR")
    balance3 = Balance("10000000000000000 wei wxHOPR")

    result = balance1 + balance2

    assert result.value == 150.00
    assert result.unit == "wxHOPR"

    result = balance1 + balance3
    assert result.value == Decimal("100.01")  # 100.00 wxHOPR + 0.01 wxHOPR in wei


def test_add_balances_edge_case():
    balance1 = Balance("0.01 wxHOPR")
    balance2 = Balance("0.02 wxHOPR")

    result = balance1 + balance2

    assert result.value == Decimal("0.03")


def test_sub_balances():
    balance1 = Balance("100.00 wxHOPR")
    balance2 = Balance("50.00 wxHOPR")

    result = balance1 - balance2

    assert result.value == 50.00
    assert result.unit == "wxHOPR"


def test_sub_balances_with_conversion():
    balance1 = Balance("100.00 wxHOPR")
    balance2 = Balance("10000000000000000 wei wxHOPR")

    result = balance1 - balance2

    assert result.value == Decimal("99.99")
    assert result.unit == "wxHOPR"


def test_div_balances():
    balance1 = Balance("100.50 wxHOPR")

    result = balance1 / 2

    assert result.value == 50.25
    assert result.unit == "wxHOPR"


def test_div_balance_with_balance():
    balance1 = Balance("100.00 wxHOPR")
    balance2 = Balance("50.00 wxHOPR")

    result = balance1 / balance2

    assert result == 2.0
