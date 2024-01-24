from test.components.utils import handle_envvars

from core.components.flags import Flags


def test_getEnvironmentFlagValue():
    Flags._cache_flags = None

    with handle_envvars(FLAG_TEST="1.0"):
        assert Flags.getEnvironmentFlagValue("test", "") == 1.0


def test_getEnvironmentFlags():
    Flags._cache_flags = None

    with handle_envvars(FLAG_TEST_1="1.0", FLAG_TEST_2="1.0", FLAG_TEST_3="1.0"):
        assert Flags.getEnvironmentFlags("") == ["test_1", "test_2", "test_3"]


def test_getEnvironmentFlagsWithPrefix():
    Flags._cache_flags = None

    with handle_envvars(
        FLAG_FUNC_TEST_1="1.0", FLAG_FUNC_TEST_2="1.0", FLAG_FUNC_TEST_3="1.0"
    ):
        assert Flags.getEnvironmentFlags("FUNC_") == ["test_1", "test_2", "test_3"]
