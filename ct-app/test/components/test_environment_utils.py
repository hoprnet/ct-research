from test.components.utils import handle_envvars

from core.components.environment_utils import EnvironmentUtils


def test_envvar():
    with handle_envvars(
        string_envvar="string-envvar", int_envvar="1", float_envvar="1.0"
    ):
        assert EnvironmentUtils.envvar("FAKE_STRING_ENVVAR", "default") == "default"
        assert EnvironmentUtils.envvar("STRING_ENVVAR", type=str) == "string-envvar"
        assert EnvironmentUtils.envvar("INT_ENVVAR", type=int) == 1
        assert EnvironmentUtils.envvar("FLOAT_ENVVAR", type=float) == 1.0


def test_envvarWithPrefix():
    with handle_envvars(
        test_envvar_2="2",
        test_envvar_1="1",
        test_envvar_3="3",
        test_envvor_4="4",
    ):
        assert EnvironmentUtils.envvarWithPrefix("TEST_ENVVAR_") == {
            "TEST_ENVVAR_1": "1",
            "TEST_ENVVAR_2": "2",
            "TEST_ENVVAR_3": "3",
        }
        assert EnvironmentUtils.envvarWithPrefix("TEST_ENVVAR_", type=int) == {
            "TEST_ENVVAR_1": 1,
            "TEST_ENVVAR_2": 2,
            "TEST_ENVVAR_3": 3,
        }
