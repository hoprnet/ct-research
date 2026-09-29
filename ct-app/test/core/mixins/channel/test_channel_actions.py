import asyncio
from unittest.mock import AsyncMock

import pytest

from core.api.response_objects import Channel
from core.mixins.channel.actions import CHANNEL_FUNDS
from core.node import Node
from core.services.channel_graph_store import ChannelGraphStore
from core.types.balance import Balance
from core.types.network_models import ChannelGraphUpdate

from test.conftest import load_channels


def build_channel(
    source: str,
    destination: str,
    status: str = "Open",
    balance: str = "1 wxHOPR",
) -> Channel:
    return Channel(
        {
            "balance": balance,
            "destination": destination,
            "source": source,
            "status": status,
        }
    )


def update(channel_id: str, channel: Channel) -> ChannelGraphUpdate:
    return ChannelGraphUpdate(channel_id=channel_id, channel=channel)


def test_channel_graph_store_removes_closed_channels():
    store = ChannelGraphStore()
    store.apply(update("0x1", build_channel("a", "b")))
    store.apply(update("0x2", build_channel("a", "c", "PendingToClose")))

    store.apply(update("0x1", build_channel("a", "b", "Closed")))

    assert [c.destination for c in store.channels()] == ["c"]


def test_channel_graph_store_sweeps_channels_missing_from_new_snapshot():
    store = ChannelGraphStore()
    store.start_generation()
    store.apply(update("0x1", build_channel("a", "b")))
    store.apply(update("0x2", build_channel("a", "c")))

    # Reconnect: the new snapshot no longer contains 0x2, which closed while disconnected.
    store.start_generation()
    store.apply(update("0x1", build_channel("a", "b", balance="2 wxHOPR")))

    assert len(store) == 2  # kept until the sweep, so the view never empties mid-snapshot
    assert store.sweep() == 1
    assert [(c.destination, c.balance) for c in store.channels()] == [("b", Balance("2 wxHOPR"))]


@pytest.mark.asyncio
async def test_rebuild_channel_views_filters_node_links_and_invalidates_cache(node: Node, mocker):
    node._cached_outgoing_open = []
    node._cached_address_to_open_channel = {}
    load_channels(
        node,
        [
            build_channel(node.address.native, "peer_a", "Open"),
            build_channel("peer_c", node.address.native, "Open"),
            build_channel("peer_d", "peer_e", "Open"),
        ],
    )
    topology = {"peer_a": Balance("1 wxHOPR")}
    mocker.patch(
        "core.mixins.channel.actions.Utils.balanceInChannels",
        new=AsyncMock(return_value=topology),
    )
    network_update_request = mocker.patch.object(node.network_update_coordinator, "request")

    await node.rebuild_channel_views()

    assert [channel.destination for channel in node.channels.outgoing] == ["peer_a"]
    assert [channel.source for channel in node.channels.incoming] == ["peer_c"]
    assert len(node.channels.all) == 3
    assert node.outgoing_channel_balances == topology
    assert node.network_state.outgoing_channel_balances == topology
    assert node._cached_outgoing_open is None
    assert node._cached_address_to_open_channel is None
    assert set(node.address_to_open_channel) == {"peer_a"}
    network_update_request.assert_called_once()


@pytest.mark.asyncio
async def test_rebuild_channel_views_reports_own_open_channel_funds(node: Node):
    load_channels(
        node,
        [
            build_channel(node.address.native, "peer_a", "Open", "3 wxHOPR"),
            build_channel(node.address.native, "peer_b", "Open", "4 wxHOPR"),
            build_channel(node.address.native, "peer_c", "PendingToClose", "100 wxHOPR"),
            build_channel("peer_d", "peer_e", "Open", "50 wxHOPR"),
        ],
    )

    await node.rebuild_channel_views()

    assert CHANNEL_FUNDS._value.get() == 7.0


@pytest.mark.asyncio
async def test_apply_channel_update_requests_view_rebuild(node: Node, mocker):
    rebuild_request = mocker.patch.object(node.channel_view_coordinator, "request")

    node.apply_channel_update(update("0x1", build_channel(node.address.native, "peer_a")))

    assert len(node.channel_graph) == len(node.channel_graph.channels())
    assert any(c.destination == "peer_a" for c in node.channel_graph.channels())
    rebuild_request.assert_called_once_with("channel_graph_update")


@pytest.mark.asyncio
async def test_subscribe_channels_starts_generation_and_applies_updates(node: Node, mocker):
    node.channel_graph = ChannelGraphStore()
    mocker.patch.object(node.channel_view_coordinator, "request")
    scheduled: list = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append(callback),
    )

    def stream_channel_graph(on_connect=None):
        async def _stream():
            assert on_connect is not None, "the subscription should pass a connect hook"
            on_connect()
            yield update("0x1", build_channel(node.address.native, "peer_a"))
            yield update("0x1", build_channel(node.address.native, "peer_a", "Closed"))
            yield update("0x2", build_channel(node.address.native, "peer_b"))
            raise asyncio.CancelledError

        return _stream()

    mocker.patch.object(
        node.blokli_repository, "stream_channel_graph", side_effect=stream_channel_graph
    )

    with pytest.raises(asyncio.CancelledError):
        await node.subscribe_channels()

    assert [c.destination for c in node.channel_graph.channels()] == ["peer_b"]
    assert [callback.__name__ for callback in scheduled] == ["_sweep"]
