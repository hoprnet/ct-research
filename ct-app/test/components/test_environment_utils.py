import os
from contextlib import contextmanager

from core.components.utils import EnvironmentUtils


@contextmanager
def handle_envvars(**kwargs):
    for key, value in kwargs.items():
        os.environ[key.upper()] = value

    try:
        yield
    finally:
        for key in kwargs.keys():
            del os.environ[key.upper()]


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


def test_checkRequiredEnvVar():
    test_folder = "test/components/test_code_for_environment"

    assert not EnvironmentUtils.checkRequiredEnvVar(test_folder)

    with handle_envvars(
        group1_var1="val11",
        group1_var2="val12",
        group2_var1="val21",
        var1="val1",
        var2="val2",
    ):
        assert EnvironmentUtils.checkRequiredEnvVar(test_folder)
