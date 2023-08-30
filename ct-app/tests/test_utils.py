import os

import pytest
from tools.utils import envvar


def test_envvar():
    """
    Test whether the envvar function correctly returns the value of an environment
    variable.
    """

    os.environ["TEST_ENVVAR"] = "test_value"

    assert envvar("TEST_ENVVAR") == "test_value"


def test_missing_envvar():
    """
    Test whether the envvar function correctly raises an exception when the environment
    variable is not found.
    """

    with pytest.raises(ValueError):
        envvar("MISSING_ENVVAR")


def test_envvar_cast():
    """
    Test whether the envvar function correctly casts the value of an environment
    variable.
    """

    os.environ["TEST_ENVVAR"] = "1"

    assert envvar("TEST_ENVVAR", type=int) == 1
