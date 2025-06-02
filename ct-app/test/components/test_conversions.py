from core.components.balance import Balance
from core.components.conversions import convert_unit


def test_convertUnit():
    assert isinstance(convert_unit("1"), int)
    assert isinstance(convert_unit("1.2"), float)
    assert isinstance(convert_unit("http://localhost:8000"), str)
    assert isinstance(convert_unit("12.01 wxHOPR"), Balance)
