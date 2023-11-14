import os

from core.components.parameters import Parameters

os.environ["ENVPREFIX_STRING"] = "random-string"
os.environ["ENVPREFIX_VALUE"] = "2"
os.environ["ENVPREFIX_DECIMAL"] = "1.2"
os.environ["ENVPREFIX_URL"] = "http://localhost:8000"


def test_get_parameters_from_environment():
    params = Parameters()("ENVPREFIX_")

    assert params.envprefix.string == os.environ.get("ENVPREFIX_STRING")
    assert params.envprefix.value == int(os.environ.get("ENVPREFIX_VALUE"))
    assert params.envprefix.decimal == float(os.environ.get("ENVPREFIX_DECIMAL"))
    assert params.envprefix.url == os.environ.get("ENVPREFIX_URL")

    assert isinstance(params.envprefix.string, str)
    assert isinstance(params.envprefix.value, int)
    assert isinstance(params.envprefix.decimal, float)
    assert isinstance(params.envprefix.url, str)
