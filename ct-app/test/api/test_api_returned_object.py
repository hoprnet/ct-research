from dataclasses import dataclass, field

from core.api.response_objects import ApiResponseObject
from core.components.balance import Balance


@dataclass(init=False)
class FooResponse(ApiResponseObject):
    foo: str = field(default="", metadata={"path": "fooInTheApi"})
    bar: float = field(default=0.0, metadata={"path": "barInTheApi"})
    baz: Balance = field(
        default_factory=lambda: Balance.zero("HOPR"), metadata={"path": "bazInTheApi"}
    )
    qux: int = field(default=0, metadata={"path": "quxInTheApi"})


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
