from core.api.response_objects import ApiResponseObject
from core.components.balance import Balance


class FooResponse(ApiResponseObject):
    keys = {"foo": "fooInTheApi", "bar": "barInTheApi", "baz": "bazInTheApi", "qux": "quxInTheApi"}


def test_parse_response_object():
    data = FooResponse(
        {
            "fooInTheApi": "value1",
            "barInTheApi": "10.1",
            "bazInTheApi": "120.1 HOPR",
            "quxInTheApi": "10",
        }
    )

    assert isinstance(data.foo, str) and data.foo == "value1"
    assert isinstance(data.bar, float) and data.bar == 10.1
    assert isinstance(data.baz, Balance) and data.baz == Balance("120.1 HOPR")
    assert isinstance(data.qux, int) and data.qux == 10
