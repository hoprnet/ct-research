from test.components.utils import handle_envvars

from core.components.environment_utils import EnvironmentUtils


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
