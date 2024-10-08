from itertools import repeat
from random import choice, choices, randint
from test.decorators_patches import patches

import pytest
import yaml
from core.components import ChannelStatus, Parameters

# needs to be imported after the patches are applied
from core.core import Core
from core.model import Peer
from core.model.economic_model import (
    Budget,
    Coefficients,
    EconomicModelLegacy,
    Equation,
    Equations,
)
from core.node import Node
from hoprd_sdk.models import ChannelInfoResponse, NodeChannelsResponse
from pytest_mock import MockerFixture


class SideEffect:
    def __init__(self):
        self.it_send_message_success = self.generator_send_message_success()
        self.it_channel_balance = self.generator_channel_balance()
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
    def generator_channel_balance():
        # yields a random integer between 50 and 100
        yield from repeat(randint(50, 100))

    @staticmethod
    def generator_node_balance():
        # yields a dict with 2 random integers between 1 and 10
        yield from repeat({"hopr": randint(1, 10), "native": randint(1, 10)})

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

    def channel_balance(self, *args, **kwargs):
        return next(self.it_channel_balance)

    def node_balance(self, *args, **kwargs):
        return next(self.it_node_balance)

    def inbox_messages(self, *args, **kwargs):
        return next(self.it_inbox_messages)


@pytest.fixture
def budget() -> Budget:
    budget = Budget()
    budget.ticket_price = 0.0001
    budget.winning_probability = 1
    return budget


@pytest.fixture
def economic_model(budget: Budget) -> EconomicModelLegacy:
    equations = Equations(
        Equation("a * x", "l <= x <= c"),
        Equation("a * c + (x - c) ** (1 / b)", "x > c"),
    )
    parameters = Coefficients(1, 1, 3, 0)

    model = EconomicModelLegacy(equations, parameters, 1, 15)
    model.budget = budget
    return model


@pytest.fixture
def peers_raw() -> list[dict]:
    return [
        {"peer_id": "id_0", "peer_address": "address_0", "reported_version": "2.0.0"},
        {"peer_id": "id_1", "peer_address": "address_1", "reported_version": "1.7.0"},
        {"peer_id": "id_2", "peer_address": "address_2", "reported_version": "1.0.3"},
        {
            "peer_id": "id_3",
            "peer_address": "address_3",
            "reported_version": "1.0.0-rc.3",
        },
        {"peer_id": "id_4", "peer_address": "address_4", "reported_version": "1.0.0"},
    ]


@pytest.fixture
def peers(peers_raw: list[dict]) -> set[Peer]:
    peers = [
        Peer(peer["peer_id"], peer["peer_address"], peer["reported_version"])
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
    channels: NodeChannelsResponse,
) -> list[Node]:
    nodes = [
        Node("localhost:9000", "random_key"),
        Node("localhost:9001", "random_key"),
        Node("localhost:9002", "random_key"),
        Node("localhost:9003", "random_key"),
        Node("localhost:9004", "random_key"),
    ]
    for idx, node in enumerate(nodes):
        mocker.patch.object(node.api, "get_address", return_value=addresses[idx])
        mocker.patch.object(node.api, "all_channels", return_value=channels)
        mocker.patch.object(
            node.api, "channel_balance", side_effect=SideEffect().channel_balance
        )

        mocker.patch.object(
            node.api, "send_message", side_effect=SideEffect().send_message_success
        )
        mocker.patch.object(
            node.api, "messages_pop_all", side_effect=SideEffect().inbox_messages
        )
        mocker.patch.object(node.api, "balances", side_effect=SideEffect().node_balance)
        mocker.patch.object(
            node.api, "peers", return_value=peers_raw[:idx] + peers_raw[idx + 1 :]
        )

        mocker.patch.object(node.api, "healthyz", return_value=True)
        mocker.patch.object(node.api, "ticket_price", return_value=0.0001)
        await node.retrieve_address()

    return nodes


@pytest.fixture
def channels(peers: set[Peer]) -> NodeChannelsResponse:
    channels = list[ChannelInfoResponse]()
    index = 0

    for src in peers:
        for dest in peers:
            if src.address == dest.address:
                continue

            channels.append(
                ChannelInfoResponse(
                    f"{1*1e18:.0f}",
                    1,
                    f"channel_{index}",
                    5,
                    dest.address.address,
                    dest.address.id,
                    src.address.address,
                    src.address.id,
                    ChannelStatus.Open,
                    0,
                )
            )

            index += 1

    return NodeChannelsResponse(all=channels, incoming=[], outgoing=[])


@pytest.fixture
async def core(mocker: MockerFixture, nodes: list[Node]) -> Core:

    params = Parameters()
    with open("./test/test_config.yaml", "r") as file:
        params.parse(yaml.safe_load(file))
    setattr(params.subgraph, "apiKey", "foo_deployer_key")

    setattr(params, "pg", Parameters())
    setattr(params.pg, "user", "user")
    setattr(params.pg, "password", "password")
    setattr(params.pg, "host", "host")
    setattr(params.pg, "port", "port")
    setattr(params.pg, "database", "database")

    core = Core(nodes, params)
    core.legacy_model.budget.ticket_price = 0.1
    core.sigmoid_model.budget.ticket_price = 0.1

    return core


@pytest.fixture
async def node(
    nodes: list[Node],
    mocker: MockerFixture,
    peers_raw: list[dict],
    channels: NodeChannelsResponse,
    addresses: dict,
) -> Node:
    node = Node("localhost", "random_key")

    mocker.patch.object(node.api, "all_channels", return_value=channels)
    mocker.patch.object(node.api, "peers", return_value=peers_raw[1:])
    mocker.patch.object(node.api, "get_address", return_value=addresses[0])
    mocker.patch.object(node.api, "balances", side_effect=SideEffect().node_balance)
    mocker.patch.object(
        node.api, "channel_balance", side_effect=SideEffect().channel_balance
    )
    mocker.patch.object(node.api, "send_message", return_value=1)
    mocker.patch.object(node.api, "healthyz", return_value=True)

    params = Parameters()
    with open("./test/test_config.yaml", "r") as file:
        params.parse(yaml.safe_load(file))
    setattr(params.subgraph, "apiKey", "foo_deployer_key")

    node.params = params

    await node.healthcheck()
    await node.retrieve_address()

    return node


for p in patches:
    p.stop()
