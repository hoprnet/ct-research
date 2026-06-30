import pytest

import tests_endurance.__main__ as endurance_main
from tests_endurance import GetChannels


def test_resolve_executor_returns_known_endurance_test():
    assert endurance_main.resolve_executor("GetChannels") is GetChannels


def test_resolve_executor_rejects_unknown_name():
    with pytest.raises(KeyError, match="Unknown executor"):
        endurance_main.resolve_executor("DoesNotExist")


def test_resolve_executor_rejects_non_endurance_symbol(monkeypatch):
    monkeypatch.setattr(endurance_main, "NotATest", object(), raising=False)

    with pytest.raises(TypeError, match="must inherit EnduranceTest"):
        endurance_main.resolve_executor("NotATest")
