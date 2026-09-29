import pytest

from core.node import Node
from core.types.balance import Balance


async def _refresh(node: Node) -> set[str]:
    await node.retrieve_peers()
    node.reconcile_peer_channels()
    await node._refresh_eligibility_once()
    return node.eligible_relayers


@pytest.fixture
def incentive(node: Node):
    # Every test peer has 4 open outgoing channels of 1 wxHOPR each.
    node.params.incentive.min_channel_balance = Balance("1 wxHOPR")
    node.params.incentive.min_outgoing_channels = 4
    return node.params.incentive


@pytest.mark.asyncio
async def test_peers_with_enough_qualifying_channels_are_eligible(node: Node, incentive):
    eligible = await _refresh(node)

    assert eligible == {"address_1", "address_2", "address_3", "address_4"}


@pytest.mark.asyncio
async def test_too_few_channels_make_peers_ineligible(node: Node, incentive):
    incentive.min_outgoing_channels = 5

    assert await _refresh(node) == set()


@pytest.mark.asyncio
async def test_channels_below_minimum_balance_do_not_count(node: Node, incentive):
    incentive.min_channel_balance = Balance("1.5 wxHOPR")

    assert await _refresh(node) == set()


@pytest.mark.asyncio
async def test_ct_nodes_and_excluded_peers_are_ineligible(node: Node, incentive):
    node.params.sessions.green_destinations = ["ADDRESS_1"]
    node.params.peer.excluded_peers = ["address_2"]

    assert await _refresh(node) == {"address_3", "address_4"}


@pytest.mark.asyncio
async def test_unreachable_peers_are_ineligible(node: Node, incentive, mocker):
    await _refresh(node)
    mocker.patch.object(node.api, "peers", return_value=[])
    node.peers["address_1"].reachable = False

    node.reconcile_peer_channels()
    await node._refresh_eligibility_once()

    assert "address_1" not in node.eligible_relayers
