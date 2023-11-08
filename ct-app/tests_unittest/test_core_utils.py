from core.components.utils import Utils

import os


def test_envvar():
    os.environ["STRING_ENVVAR"] = "string_envvar"
    os.environ["INT_ENVVAR"] = "1"
    os.environ["FLOAT_ENVVAR"] = "1.0"

    assert Utils.envvar("TEST_ENVVAR", "default") == "default"
    assert Utils.envvar("STRING_ENVVAR", type=str) == "string_envvar"
    assert Utils.envvar("INT_ENVVAR", type=int) == 1
    assert Utils.envvar("FLOAT_ENVVAR", type=float) == 1.0
