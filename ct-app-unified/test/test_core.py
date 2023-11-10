from unittest import mock

import pytest
from core.core import CTCore
from core.node import Node

NODE_COUNT = 3


@pytest.fixture
def nodes(count: int = NODE_COUNT):
    result = []
    for id in range(count):
        node = Node(f"host_{id}", f"random_key_{id}")
        result.append(node)

    return result


@pytest.fixture
def ctcore():
    instance = CTCore()

    return instance


@pytest.mark.asyncio
async def test_app(ctcore: CTCore, nodes: list[Node]):
    for node in nodes:
        print(node)

    ctcore.nodes = nodes

    await ctcore.start()


@pytest.mark.asyncio
@mock.patch("core.components.hoprd_api.HoprdAPI.balances")
async def test_test(mock_balances, ctcore: CTCore, nodes: list[Node]):
    nodes[0].retrieve_balances()

    mock_balances.assert_called_once()
