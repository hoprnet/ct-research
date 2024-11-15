from core.api.api_returned_objects import ApiReturnedObject


class FooReturnedtObject(ApiReturnedObject):
    keys = {"foo": "fooInTheApi", "bar": "barInTheApi"}


def test_parse_returned_object():
    data = FooReturnedtObject({"fooInTheApi": "value1", "barInTheApi": "value2"})

    assert data.foo == "value1"
    assert data.bar == "value2"
