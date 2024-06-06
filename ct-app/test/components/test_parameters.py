import os

from core.components.parameters import Parameters
import pytest

params_from_yaml = {
        "parent1": "value1",
        "parent2": {
            "child1": "value2",
            "child2": {
                "grandchild1": "value3"
            }
        }
    }

def test_parse():
    params = Parameters()
    params.parse(params_from_yaml)

    assert params.parent1 == "value1"
    assert params.parent2.child1 == "value2"
    assert params.parent2.child2.grandchild1 == "value3"

def test_overrides():
    os.environ["OVERRIDES_PARENT1"] = "value1-override"
    os.environ["OVERRIDES_PARENT2_CHILD1"] = "value2-override"
    os.environ["OVERRIDES_PARENT2_CHILD2_GRANDCHILD1"] = "value3-override"

    params = Parameters()
    params.parse(params_from_yaml)
    params.overrides("OVERRIDES_")

    assert params.parent1 == "value1-override"
    assert params.parent2.child1 == "value2-override"
    assert params.parent2.child2.grandchild1 == "value3-override"

    del os.environ["OVERRIDES_PARENT1"]
    del os.environ["OVERRIDES_PARENT2_CHILD1"]
    del os.environ["OVERRIDES_PARENT2_CHILD2_GRANDCHILD1"]

def test_overrides_raises():
    os.environ["OVERRIDES_PARENT3"] = "value1-override"
    params = Parameters()
    params.parse(params_from_yaml)
    
    with pytest.raises(KeyError):
        params.overrides("OVERRIDES_")

    del os.environ["OVERRIDES_PARENT3"]

def test_from_env():
    os.environ["ENVPREFIX_STRING"] = "random-string"
    os.environ["ENVPREFIX_VALUE"] = "2"
    os.environ["ENVPREFIX_DECIMAL"] = "1.2"
    os.environ["ENVPREFIX_URL"] = "http://localhost:8000"

    params = Parameters()
    params.from_env("ENVPREFIX")

    assert params.envprefix.string == os.environ.get("ENVPREFIX_STRING")
    assert params.envprefix.value == int(os.environ.get("ENVPREFIX_VALUE"))
    assert params.envprefix.decimal == float(os.environ.get("ENVPREFIX_DECIMAL"))
    assert params.envprefix.url == os.environ.get("ENVPREFIX_URL")

    assert isinstance(params.envprefix.string, str)
    assert isinstance(params.envprefix.value, int)
    assert isinstance(params.envprefix.decimal, float)
    assert isinstance(params.envprefix.url, str)

    del os.environ["ENVPREFIX_STRING"]
    del os.environ["ENVPREFIX_VALUE"]
    del os.environ["ENVPREFIX_DECIMAL"]
    del os.environ["ENVPREFIX_URL"]

def test__convert():
    params = Parameters()

    assert isinstance(params._convert("1"), int)
    assert isinstance(params._convert("1.2"), float)
    assert isinstance(params._convert("http://localhost:8000"), str)