from itertools import repeat
from random import randint
from test.decorators_patches import patches

import pytest
import yaml
from pytest_mock import MockerFixture

from core.api.response_objects import (
    Addresses,
    Balances,
    Channel,
    Channels,
    ConnectedPeer,
)
from core.components import Peer
from core.components.balance import Balance
from core.components.config_parser import LegacyParams, Parameters
from core.core import Core
from core.node import Node


class SideEffect:
    def __init__(self):
        self.it_node_balance = self.generator_node_balance()

    @staticmethod
    def generator_node_balance():
        yield from repeat(
            Balances({"hopr": f"{randint(1, 10)} wxHOPR", "native": f"{randint(1, 10)} xDai"})
        )

    def node_balance(self, *args, **kwargs):
        return next(self.it_node_balance)


@pytest.fixture
def economic_model() -> LegacyParams:
    return LegacyParams(
        {
            "proportion": 1,
            "apr": 15,
            "coefficients": {"a": 1, "b": 1, "c": "3 wxHOPR", "l": "0 wxHOPR"},
            "equations": {
                "fx": {"formula": "a * x", "condition": "l <= x <= c"},
                "gx": {"formula": "a * c + (x - c) ** (1 / b)", "condition": "x > c"},
            },
        }
    )


@pytest.fixture
def peers_raw() -> list[dict]:
    return [
        {"address": "address_0", "reportedVersion": "2.0.0"},
        {"address": "address_1", "reportedVersion": "2.7.0"},
        {"address": "address_2", "reportedVersion": "2.0.8"},
        {
            "address": "address_3",
            "reportedVersion": "2.1.0-rc.3",
        },
        {"address": "address_4", "reportedVersion": "2.0.9"},
    ]


@pytest.fixture
def peers(peers_raw: list[dict]) -> set[Peer]:
    peers = [Peer(peer["address"], peer["reportedVersion"]) for peer in peers_raw]
    for peer in peers:
        peer.safe_balance = Balance(f"{randint(100, 200)} wxHOPR")
        peer.channel_balance = Balance(f"{randint(10, 50)} wxHOPR")

    return set(peers)


@pytest.fixture
def addresses() -> list[dict]:
    return [
        {"native": "address_0"},
        {"native": "address_1"},
        {"native": "address_2"},
        {"native": "address_3"},
        {"native": "address_4"},
    ]


@pytest.fixture
async def nodes(
    mocker: MockerFixture,
    peers: set[Peer],
    addresses: list[dict],
    peers_raw: list[dict],
    channels: Channels,
) -> list[Node]:
    nodes = [
        Node("localhost:9000", "random_key"),
        Node("localhost:9001", "random_key"),
        Node("localhost:9002", "random_key"),
        Node("localhost:9003", "random_key"),
        Node("localhost:9004", "random_key"),
    ]
    for idx, node in enumerate(nodes):
        mocker.patch.object(node.api, "get_address", return_value=Addresses(addresses[idx]))
        mocker.patch.object(node.api, "channels", return_value=channels)
        mocker.patch.object(node.api, "balances", side_effect=SideEffect().node_balance)
        mocker.patch.object(
            node.api,
            "peers",
            return_value=[ConnectedPeer(peer) for peer in peers_raw[:idx] + peers_raw[idx + 1 :]],
        )

        mocker.patch.object(node.api, "healthyz", return_value=True)
        mocker.patch.object(node.api, "ticket_price", return_value=Balance("0.0001 wxHOPR"))
        await node.retrieve_address()

    return nodes


@pytest.fixture
def channels(peers: set[Peer]) -> Channels:
    all_channels = list[Channel]()
    index = 0

    for src in peers:
        for dest in peers:
            if src.address == dest.address:
                continue

            all_channels.append(
                Channel(
                    {
                        "balance": "1 wxHOPR",
                        "id": f"channel_{index}",
                        "destination": dest.address.native,
                        "source": src.address.native,
                        "status": "Open",
                    }
                )
            )

            index += 1

    channels = Channels({})
    channels.all = all_channels

    return channels


@pytest.fixture
async def core(mocker: MockerFixture, nodes: list[Node]) -> Core:

    with open("./test/test_config.yaml", "r") as file:
        params = Parameters(yaml.safe_load(file))
    setattr(params.subgraph, "api_key", "foo_deployer_key")

    core = Core(nodes, params)

    return core


@pytest.fixture
async def node(
    nodes: list[Node],
    mocker: MockerFixture,
    peers_raw: list[dict],
    channels: Channels,
    addresses: dict,
) -> Node:
    node = Node("localhost", "random_key")

    mocker.patch.object(node.api, "channels", return_value=channels)
    mocker.patch.object(
        node.api, "peers", return_value=[ConnectedPeer(peer) for peer in peers_raw[1:]]
    )
    mocker.patch.object(node.api, "get_address", return_value=Addresses(addresses[0]))
    mocker.patch.object(node.api, "balances", side_effect=SideEffect().node_balance)
    # mocker.patch.object(node.api, "send_message", return_value=1)
    mocker.patch.object(node.api, "healthyz", return_value=True)

    params = Parameters()
    with open("./test/test_config.yaml", "r") as file:
        params = Parameters(yaml.safe_load(file))
    setattr(params.subgraph, "api_key", "foo_deployer_key")

    node.params = params

    await node.healthcheck()
    await node.retrieve_address()

    return node


for p in patches:
    p.stop()
