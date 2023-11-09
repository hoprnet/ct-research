from core.components.parameters import Parameters
import os

os.environ["ENVPREFIX_STRING"] = "random-string"
os.environ["ENVPREFIX_VALUE"] = "2"
os.environ["ENVPREFIX_DECIMAL"] = "1.2"
os.environ["ENVPREFIX_URL"] = "http://localhost:8000"


def test_get_parameters_from_environment():
    params = Parameters()(env_prefix="ENVPREFIX_")

    assert params.string == os.environ.get("ENVPREFIX_STRING")
    assert params.value == int(os.environ.get("ENVPREFIX_VALUE"))
    assert params.decimal == float(os.environ.get("ENVPREFIX_DECIMAL"))
    assert params.url == os.environ.get("ENVPREFIX_URL")

    assert isinstance(params.string, str)
    assert isinstance(params.value, int)
    assert isinstance(params.decimal, float)
    assert isinstance(params.url, str)
