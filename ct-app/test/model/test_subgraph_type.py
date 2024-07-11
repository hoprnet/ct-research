from core.model.subgraph import SubgraphType


def test_callables():
    types = SubgraphType.callables()

    assert SubgraphType.NONE not in types
    assert SubgraphType.DEFAULT in types
    assert SubgraphType.BACKUP in types


def test_toInt():
    assert SubgraphType.toInt(SubgraphType.NONE) == -1
    assert SubgraphType.toInt(SubgraphType.DEFAULT) == 0
    assert SubgraphType.toInt(SubgraphType.BACKUP) == 1
