from core.subgraph import Mode


def test_callables():
    types = Mode.callables()

    assert Mode.NONE not in types
    assert Mode.DEFAULT in types
    assert Mode.BACKUP in types


def test_toInt():
    assert Mode.toInt(Mode.NONE) == -1
    assert Mode.toInt(Mode.DEFAULT) == 0
    assert Mode.toInt(Mode.BACKUP) == 1
