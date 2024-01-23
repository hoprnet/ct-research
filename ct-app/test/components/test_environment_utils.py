import os
from pathlib import Path

from core.components.utils import EnvironmentUtils


def test_envvar():
    os.environ["STRING_ENVVAR"] = "string-envvar"
    os.environ["INT_ENVVAR"] = "1"
    os.environ["FLOAT_ENVVAR"] = "1.0"

    assert EnvironmentUtils.envvar("FAKE_STRING_ENVVAR", "default") == "default"
    assert EnvironmentUtils.envvar("STRING_ENVVAR", type=str) == "string-envvar"
    assert EnvironmentUtils.envvar("INT_ENVVAR", type=int) == 1
    assert EnvironmentUtils.envvar("FLOAT_ENVVAR", type=float) == 1.0

    del os.environ["STRING_ENVVAR"]
    del os.environ["INT_ENVVAR"]
    del os.environ["FLOAT_ENVVAR"]


def test_envvarWithPrefix():
    os.environ["TEST_ENVVAR_2"] = "2"
    os.environ["TEST_ENVVAR_1"] = "1"
    os.environ["TEST_ENVVAR_3"] = "3"
    os.environ["TEST_ENVVOR_4"] = "3"

    assert EnvironmentUtils.envvarWithPrefix("TEST_ENVVAR_", type=int) == {
        "TEST_ENVVAR_1": 1,
        "TEST_ENVVAR_2": 2,
        "TEST_ENVVAR_3": 3,
    }

    del os.environ["TEST_ENVVAR_1"]
    del os.environ["TEST_ENVVAR_2"]
    del os.environ["TEST_ENVVAR_3"]
    del os.environ["TEST_ENVVOR_4"]


def test_checkRequiredEnvVar():
    test_folder = Path(__file__).parent.joinpath("test_code")
    file = test_folder.joinpath("test_main.py")
    test_folder.mkdir(exist_ok=False)
    file.touch(exist_ok=False)

    file.write_text(
        """
        var1 = params.group1.var1
        var2 = params.group1.var2
        var3 = params.group2.var1
        var4 = params.var1
        """
    )

    assert not EnvironmentUtils.checkRequiredEnvVar(test_folder)

    os.environ["GROUP1_VAR1"] = "val11"
    os.environ["GROUP1_VAR2"] = "val12"
    os.environ["GROUP2_VAR1"] = "val21"
    os.environ["VAR1"] = "val1"

    assert EnvironmentUtils.checkRequiredEnvVar(test_folder)

    # cleanup
    file.unlink()
    test_folder.rmdir()
