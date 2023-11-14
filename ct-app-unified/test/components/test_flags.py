from core.components.flags import Flags

import os


def test_getEnvironmentFlagValue():
    Flags._cache_flags = None

    os.environ["FLAG_TEST"] = "1.0"
    assert Flags.getEnvironmentFlagValue("test", "") == 1.0
    del os.environ["FLAG_TEST"]


def test_getEnvironmentFlags():
    Flags._cache_flags = None

    os.environ["FLAG_TEST_1"] = "1.0"
    os.environ["FLAG_TEST_2"] = "1.0"
    os.environ["FLAG_TEST_3"] = "1.0"

    assert Flags.getEnvironmentFlags("") == ["test_1", "test_2", "test_3"]

    del os.environ["FLAG_TEST_1"]
    del os.environ["FLAG_TEST_2"]
    del os.environ["FLAG_TEST_3"]


def test_getEnvironmentFlagsWithPrefix():
    Flags._cache_flags = None

    os.environ["FLAG_FUNC_TEST_1"] = "1.0"
    os.environ["FLAG_FUNC_TEST_2"] = "1.0"
    os.environ["FLAG_FUNC_TEST_3"] = "1.0"

    assert Flags.getEnvironmentFlags("FUNC_") == ["test_1", "test_2", "test_3"]

    del os.environ["FLAG_FUNC_TEST_1"]
    del os.environ["FLAG_FUNC_TEST_2"]
    del os.environ["FLAG_FUNC_TEST_3"]
