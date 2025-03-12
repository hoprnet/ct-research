from core.subgraph import Mode


def test_callables():
    types = Mode.callables()

    assert Mode.NONE not in types
    assert Mode.DEFAULT in types
    assert Mode.BACKUP in types


def test_to_int():
    assert Mode.to_int(Mode.NONE) == -1
    assert Mode.to_int(Mode.DEFAULT) == 0
    assert Mode.to_int(Mode.BACKUP) == 1
