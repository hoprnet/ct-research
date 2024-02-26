import os
from test.components.utils import handle_envvars

from core.components.parameters import Parameters


def test_get_parameters_from_environment():
    with handle_envvars(
        envprefix_string="random-string",
        envprefix_value="2",
        envprefix_decimal="1.2",
        envprefix_url="http://localhost:8000",
    ):
        params = Parameters()("ENVPREFIX_")

        assert params.envprefix.string == os.environ.get("ENVPREFIX_STRING")
        assert params.envprefix.value == int(os.environ.get("ENVPREFIX_VALUE"))
        assert params.envprefix.decimal == float(os.environ.get("ENVPREFIX_DECIMAL"))
        assert params.envprefix.url == os.environ.get("ENVPREFIX_URL")

        assert isinstance(params.envprefix.string, str)
        assert isinstance(params.envprefix.value, int)
        assert isinstance(params.envprefix.decimal, float)
        assert isinstance(params.envprefix.url, str)
