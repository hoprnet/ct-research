from copy import deepcopy
from itertools import repeat
from random import choice, choices, randint
from test.decorators_patches import patches

import pytest
from core.components.parameters import Parameters
from core.model.economic_model import (
    BudgetParameters,
    EconomicModel,
    Equation,
    Equations,
)
from core.model.economic_model import Parameters as EMParameters
from core.model.peer import Peer
from database import Utils as DBUtils
from hoprd_sdk.models import ChannelInfoResponse, NodeChannelsResponse
from pytest_mock import MockerFixture

for p in patches:
    p.start()

# needs to be imported after the patches are applied
from core.core import Core  # noqa: E402
from core.node import Node  # noqa: E402


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
def economic_model() -> EconomicModel:
    equations = Equations(
        Equation("a * x", "l <= x <= c"),
        Equation("a * c + (x - c) ** (1 / b)", "x > c"),
    )
    parameters = EMParameters(1, 1, 3, 0)
    budget = BudgetParameters(100, 15, 0.25, 2, 1)
    return EconomicModel(equations, parameters, budget)


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
def peers(peers_raw: list[dict], economic_model: EconomicModel) -> list[Peer]:
    peers = [
        Peer(peer["peer_id"], peer["peer_address"], peer["reported_version"])
        for peer in peers_raw
    ]
    for peer in peers:
        peer.economic_model = economic_model
        peer.reward_probability = 0.02
        peer.safe_balance = randint(100, 200)
        peer.channel_balance = randint(10, 50)
        peer.economic_model.budget.ticket_price = 0.01

    return peers


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
def nodes() -> list[Node]:
    return [
        Node("localhost:9000", "random_key"),
        Node("localhost:9001", "random_key"),
        Node("localhost:9002", "random_key"),
        Node("localhost:9003", "random_key"),
        Node("localhost:9004", "random_key"),
    ]


@pytest.fixture
def channels(peers: list[Peer]) -> NodeChannelsResponse:
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
                    "Open",
                    0,
                )
            )

            index += 1

    return NodeChannelsResponse(all=channels, incoming=[], outgoing=[])


@pytest.fixture
async def core(
    mocker: MockerFixture,
    nodes: list[Node],
    peers: list[Peer],
    addresses: list[dict],
    channels: NodeChannelsResponse,
) -> Core:
    core = Core()
    core.nodes = nodes

    for idx, node in enumerate(core.nodes):
        mocker.patch.object(node.peers, "get", return_value=peers)
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

        setattr(node.params, "distribution", Parameters())
        setattr(node.params.distribution, "delay_between_two_messages", 0.001)


    mocker.patch.object(DBUtils, "peerIDToInt", return_value=0)

    mocker.patch.object(core.api, "healthyz", return_value=True)
    mocker.patch.object(core.api, "startedz", return_value=True)
    mocker.patch.object(core.api, "ticket_price", return_value=0.01)

    params = Parameters()
    setattr(params, "subgraph", Parameters())

    setattr(params.subgraph, "safes_balance_url", "safes default url")
    setattr(params.subgraph, "safes_balance_url_backup", "safes backup url")    
    setattr(params.subgraph, "staking_url", "staking default url")
    setattr(params.subgraph, "staking_url_backup", "staking backup url")
    setattr(params.subgraph, "wxhopr_txs_url", "wxhopr default url")
    setattr(params.subgraph, "wxhopr_txs_url_backup", "wxhopr backup url")

    setattr(params, "peer", Parameters())
    setattr(params.peer, "min_version", "0.0.0")

    setattr(params, "economic_model", Parameters())
    setattr(params.economic_model, "min_safe_allowance", 0.000001)
    setattr(params.economic_model, "filename", "file")

    setattr(params, "gcp", Parameters())
    setattr(params.gcp, "bucket", "ctdapp-bucket")
    setattr(params.gcp, "file_prefix", "prefix")
    setattr(params.gcp, "folder", "ctdapp-folder")

    setattr(params, "distribution", Parameters())
    setattr(params.distribution, "message_delivery_delay", 1)
    setattr(params.distribution, "delay_between_two_messages", 0.01)


    core.post_init(nodes, params)

    for idx, node in enumerate(core.nodes):
        await node._retrieve_address()

    await core.healthcheck()
    await core._retrieve_address()
    
    return core


@pytest.fixture
async def node(
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
    mocker.patch.object(node.api, "startedz", side_effect=True)

    setattr(node.params, "distribution", Parameters())
    setattr(node.params.distribution, "delay_between_two_messages", 0.2)

    await node.healthcheck()
    await node._retrieve_address()

    return node


for p in patches:
    p.stop()
