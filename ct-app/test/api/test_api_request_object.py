from core.api.api_request_objects import ApiRequestObject


class FooRequestObject(ApiRequestObject):
    keys = {
        "foo": "fooForApi",
        "bar": "barForApi",
    }

    def __init__(self, foo: str, bar: str):
        super().__init__(vars())


def test_parse_request_object_to_dict():
    data = FooRequestObject("value1", "value2")

    assert data.foo == data.as_dict["fooForApi"] == "value1"
    assert data.bar == data.as_dict["barForApi"] == "value2"


def test_parse_request_object_to_string():
    data = FooRequestObject("value1", "value2")

    assert data.as_header_string == "fooForApi=value1&barForApi=value2"
