from dataclasses import dataclass

from core.api.request_objects import ApiRequestObject, api_field


@dataclass
class FooRequestObject(ApiRequestObject):
    foo: str = api_field("fooForApi")
    bar: str = api_field("barForApi")


def test_parse_request_object_to_dict():
    data = FooRequestObject("value1", "value2")

    assert data.foo == data.as_dict["fooForApi"] == "value1"
    assert data.bar == data.as_dict["barForApi"] == "value2"


def test_parse_request_object_to_string():
    data = FooRequestObject("value1", "value2")

    assert data.as_header_string == "fooForApi=value1&barForApi=value2"
