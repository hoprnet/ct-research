from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest
import yaml
from pytest_mock import MockerFixture

from core.api.response_objects import Addresses, Balances, Session
from core.types.peer import Peer
from core.config_parser import Parameters
from core.types.message_queue import MessageQueue
from core.types.singleton import Singleton
from core.node import Node


@pytest.fixture
def mock_sessions():
    def _create_session(relayer: str, port: Optional[int] = None) -> Session:
        if port is None:
            port = 9000 + abs(hash(relayer)) % 1000

        return Session(
            {
                "ip": "127.0.0.1",
                "port": port,
                "protocol": "udp",
                "target": relayer,
                "hoprMtu": 1002,
                "surbLen": 395,
            }
        )

    return _create_session


@pytest.fixture
async def session_node(mocker: MockerFixture) -> Node:
    node = Node("http://localhost:3001", "test_token", Parameters())

    mocker.patch.object(node.api, "address", return_value=Addresses({"native": "node_address"}))
    mocker.patch.object(
        node.api,
        "balances",
        return_value=Balances(
            {
                "hopr": "100 wxHOPR",
                "native": "10 xDai",
                "safeHopr": "50 wxHOPR",
                "safeNative": "5 xDai",
            }
        ),
    )
    mocker.patch.object(node.api, "healthyz", return_value=True)

    cfg = Path(__file__).resolve().parents[3] / "test_config.yaml"
    with cfg.open("r") as file:
        params = Parameters(yaml.safe_load(file))

    setattr(params.flags.node, "observe_message_queue", MagicMock(value=1))
    setattr(params.flags.node, "maintain_sessions", MagicMock(value=1))

    node.params = params
    await node.retrieve_address()

    node.sessions = {}
    node.session_destinations = []
    node.connected = True

    return node


@pytest.fixture(autouse=True)
def clear_message_queue():
    if MessageQueue in Singleton._instances:
        del Singleton._instances[MessageQueue]
    yield
    if MessageQueue in Singleton._instances:
        del Singleton._instances[MessageQueue]


@pytest.fixture
def mock_peers() -> dict[str, Peer]:
    peers = {}
    for addr in [f"peer_{i}" for i in range(5)]:
        peers[addr] = Peer(addr)
    return peers
