from core.api.response_objects import ApiResponseObject


class FooResponse(ApiResponseObject):
    keys = {"foo": "fooInTheApi", "bar": "barInTheApi"}


def test_parse_response_object():
    data = FooResponse({"fooInTheApi": "value1", "barInTheApi": "value2"})

    assert data.foo == "value1"
    assert data.bar == "value2"
