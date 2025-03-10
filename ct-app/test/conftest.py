from itertools import repeat
from random import choice, choices, randint
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
from core.components import Parameters, Peer
from core.components.parameters import LegacyParams

# needs to be imported after the patches are applied
from core.core import Core
from core.node import Node


class SideEffect:
    def __init__(self):
        self.it_send_message_success = self.generator_send_message_success()
        self.it_node_balance = self.generator_node_balance()
        self.it_inbox_messages = self.generator_inbox_messages()

    @staticmethod
    def generator_send_message_success():
        # yields 1 95% of the time and 0 5% of the time
        rate = 0.95
        zeros = int(100 * (1 - rate))
        ones = int(100 * rate)
        yield from repeat(choice([0] * zeros + [1] * ones))

    @staticmethod
    def generator_node_balance():
        # yields a dict with 2 random integers between 1 and 10
        yield from repeat(Balances({"hopr": randint(1, 10), "native": randint(1, 10)}))

    @staticmethod
    def generator_inbox_messages():
        # yields a list of 10 random characters repeated 2 to 10 times
        yield from repeat(
            [
                choices("abcdefghijklmnopqrstuvwxyz ", k=10)
                for _ in range(randint(2, 10))
            ]
        )

    def send_message_success(self, *args, **kwargs):
        return next(self.it_send_message_success)

    def node_balance(self, *args, **kwargs):
        return next(self.it_node_balance)

    def inbox_messages(self, *args, **kwargs):
        return next(self.it_inbox_messages)


@pytest.fixture
def economic_model() -> LegacyParams:
    return LegacyParams(
        {
            "proportion": 1,
            "apr": 15,
            "coefficients": {"a": 1, "b": 1, "c": 3, "l": 0},
            "equations": {
                "fx": {"formula": "a * x", "condition": "l <= x <= c"},
                "gx": {"formula": "a * c + (x - c) ** (1 / b)", "condition": "x > c"},
            },
        }
    )


@pytest.fixture
def peers_raw() -> list[dict]:
    return [
        {"peerId": "id_0", "peerAddress": "address_0", "reportedVersion": "2.0.0"},
        {"peerId": "id_1", "peerAddress": "address_1", "reportedVersion": "2.7.0"},
        {"peerId": "id_2", "peerAddress": "address_2", "reportedVersion": "2.0.8"},
        {
            "peerId": "id_3",
            "peerAddress": "address_3",
            "reportedVersion": "2.1.0-rc.3",
        },
        {"peerId": "id_4", "peerAddress": "address_4", "reportedVersion": "2.0.9"},
    ]


@pytest.fixture
def peers(peers_raw: list[dict]) -> set[Peer]:
    peers = [
        Peer(peer["peerId"], peer["peerAddress"], peer["reportedVersion"])
        for peer in peers_raw
    ]
    for peer in peers:
        peer.safe_balance = randint(100, 200)
        peer.channel_balance = randint(10, 50)

    return set(peers)


@pytest.fixture
def addresses() -> list[dict]:
    return [
        {"hopr": "id_0", "native": "address_0"},
        {"hopr": "id_1", "native": "address_1"},
        {"hopr": "id_2", "native": "address_2"},
        {"hopr": "id_3", "native": "address_3"},
        {"hopr": "id_4", "native": "address_4"},
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
        mocker.patch.object(
            node.api, "get_address", return_value=Addresses(addresses[idx])
        )
        mocker.patch.object(node.api, "channels", return_value=channels)
        mocker.patch.object(node.api, "balances", side_effect=SideEffect().node_balance)
        mocker.patch.object(
            node.api,
            "peers",
            return_value=[
                ConnectedPeer(peer) for peer in peers_raw[:idx] + peers_raw[idx + 1 :]
            ],
        )

        mocker.patch.object(node.api, "healthyz", return_value=True)
        mocker.patch.object(node.api, "ticket_price", return_value=0.0001)
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
                        "balance": f"{1*1e18:.0f}",
                        "id": f"channel_{index}",
                        "destinationAddress": dest.address.native,
                        "destinationPeerId": dest.address.hopr,
                        "sourceAddress": src.address.native,
                        "sourcePeerId": src.address.hopr,
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
