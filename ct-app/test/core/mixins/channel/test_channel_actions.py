import inspect
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from core.api.response_objects import Channel, Channels
from core.types.peer import Peer
from core.types.balance import Balance
from core.components.node_helper import NodeHelper
from core.node import Node


def build_channel(
    channel_id: str,
    source: str,
    destination: str,
    status: str = "Open",
    balance: str = "1 wxHOPR",
) -> Channel:
    return Channel(
        {
            "balance": balance,
            "channelId": channel_id,
            "destination": destination,
            "source": source,
            "status": status,
        }
    )


def enable_channel_flag(node: Node, name: str) -> None:
    setattr(getattr(node.params.flags.node, name), "value", 1)


async def invoke_action(node: Node, name: str):
    method = inspect.unwrap(getattr(type(node), name))
    return await method(node)


@pytest.mark.asyncio
async def test_get_total_channel_funds_uses_outgoing_balance_sum(node: Node, mocker):
    enable_channel_flag(node, "get_total_channel_funds")
    await node.retrieve_channels()
    expected = Balance("7 wxHOPR")
    mocker.patch(
        "core.mixins.channel.actions.Utils.balanceInChannels",
        new=AsyncMock(return_value={node.address.native: expected}),
    )

    balance = await invoke_action(node, "get_total_channel_funds")

    assert balance == expected


@pytest.mark.asyncio
async def test_retrieve_channels_filters_node_links_and_invalidates_cache(node: Node, mocker):
    enable_channel_flag(node, "retrieve_channels")
    node._cached_outgoing_open = []
    node._cached_incoming_open = []
    node._cached_outgoing_pending = []
    node._cached_outgoing_not_closed = []
    node._cached_address_to_open_channel = {}

    all_channels = [
        build_channel("out-open", node.address.native, "peer_a", "Open"),
        build_channel("out-closed", node.address.native, "peer_b", "Closed"),
        build_channel("in-open", "peer_c", node.address.native, "Open"),
        build_channel("foreign", "peer_d", "peer_e", "Open"),
    ]
    channels = Channels({})
    channels.all = all_channels
    channels.outgoing = []
    channels.incoming = []

    topology = {"peer_a": Balance("1 wxHOPR")}
    mocker.patch.object(node.api, "channels", new=AsyncMock(return_value=channels))
    mocker.patch(
        "core.mixins.channel.actions.Utils.balanceInChannels",
        new=AsyncMock(return_value=topology),
    )

    await invoke_action(node, "retrieve_channels")

    assert [channel.id for channel in node.channels.outgoing] == ["out-open"]
    assert [channel.id for channel in node.channels.incoming] == ["in-open"]
    assert node.outgoing_channel_balances == topology
    assert node.network_state.outgoing_channel_balances == topology
    assert node._cached_outgoing_open is None
    assert node._cached_incoming_open is None
    assert node._cached_outgoing_pending is None
    assert node._cached_outgoing_not_closed is None
    assert node._cached_address_to_open_channel is None


@pytest.mark.asyncio
async def test_fund_channels_schedules_only_low_balance_known_peer_channels(node: Node, mocker):
    enable_channel_flag(node, "fund_channels")
    node.peers = {"peer_low": Peer("peer_low"), "peer_other": Peer("peer_other")}
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel("low-peer", node.address.native, "peer_low", balance="0.01 wxHOPR"),
        build_channel("low-unknown", node.address.native, "peer_unknown", balance="0.01 wxHOPR"),
        build_channel("healthy", node.address.native, "peer_other", balance="5 wxHOPR"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await invoke_action(node, "fund_channels")

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == NodeHelper.fund_channel.__name__
    assert args[0] is node.api
    assert args[1].id == "low-peer"
    assert args[2] == node.params.channel.funding_amount
    assert kwargs == {"publish_to_task_set": False}


@pytest.mark.asyncio
async def test_close_old_channels_tracks_new_peers_and_closes_only_stale_channels(
    node: Node, mocker
):
    enable_channel_flag(node, "close_old_channels")
    stale_time = datetime.now() - timedelta(seconds=node.params.channel.max_age.value + 5)
    recent_time = datetime.now() - timedelta(seconds=node.params.channel.max_age.value / 2)

    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel("stale", node.address.native, "peer_stale"),
        build_channel("recent", node.address.native, "peer_recent"),
        build_channel("new", node.address.native, "peer_new"),
    ]
    node.channels.incoming = []
    node.peer_history = {"peer_stale": stale_time, "peer_recent": recent_time}
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await invoke_action(node, "close_old_channels")

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == NodeHelper.close_channel.__name__
    assert args[0] is node.api
    assert args[1].id == "stale"
    assert args[2] == "old_closed"
    assert kwargs == {"publish_to_task_set": False}
    assert "peer_new" in node.peer_history
    assert node.peer_history["peer_new"] >= stale_time


@pytest.mark.asyncio
async def test_close_pending_channels_schedules_pending_only(node: Node, mocker):
    enable_channel_flag(node, "close_pending_channels")
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel("pending", node.address.native, "peer_pending", "PendingToClose"),
        build_channel("open", node.address.native, "peer_open", "Open"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await invoke_action(node, "close_pending_channels")

    assert len(scheduled) == 1
    assert scheduled[0][0].__name__ == NodeHelper.close_channel.__name__
    assert scheduled[0][1][1].id == "pending"
    assert scheduled[0][1][2] == "pending_closed"


@pytest.mark.asyncio
async def test_close_incoming_channels_schedules_all_incoming_open(node: Node, mocker):
    enable_channel_flag(node, "close_incoming_channels")
    node.channels = Channels({})
    node.channels.outgoing = []
    node.channels.incoming = [
        build_channel("incoming-a", "peer_a", node.address.native, "Open"),
        build_channel("incoming-b", "peer_b", node.address.native, "Open"),
    ]
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await invoke_action(node, "close_incoming_channels")

    assert [item[1][1].id for item in scheduled] == ["incoming-a", "incoming-b"]
    assert all(item[0].__name__ == NodeHelper.close_channel.__name__ for item in scheduled)
    assert all(item[1][2] == "incoming_closed" for item in scheduled)


@pytest.mark.asyncio
async def test_open_channels_skips_peers_with_open_or_pending_channels(node: Node, mocker):
    enable_channel_flag(node, "open_channels")
    node.peers = {
        "peer_open": Peer("peer_open"),
        "peer_pending": Peer("peer_pending"),
        "peer_missing": Peer("peer_missing"),
    }
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel("open", node.address.native, "peer_open", "Open"),
        build_channel("pending", node.address.native, "peer_pending", "PendingToClose"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await invoke_action(node, "open_channels")

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == NodeHelper.open_channel.__name__
    assert args[0] is node.api
    assert args[1] == "peer_missing"
    assert args[2] == node.params.channel.funding_amount
    assert kwargs == {"publish_to_task_set": False}
