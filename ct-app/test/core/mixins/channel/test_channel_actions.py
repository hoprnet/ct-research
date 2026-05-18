from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from core.api.response_objects import Channel, Channels
from core.types.peer import Peer
from core.types.balance import Balance
from core.components.node_helper import NodeHelper
from core.node import Node


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


@pytest.mark.asyncio
async def test_get_total_channel_funds_uses_outgoing_balance_sum(node: Node, mocker):
    await node.retrieve_channels()
    expected = Balance("7 wxHOPR")
    mocker.patch(
        "core.mixins.channel.actions.Utils.balanceInChannels",
        new=AsyncMock(return_value={node.address.native: expected}),
    )

    balance = await node.get_total_channel_funds()

    assert balance == expected


@pytest.mark.asyncio
async def test_retrieve_channels_filters_node_links_and_invalidates_cache(node: Node, mocker):
    node._cached_outgoing_open = []
    node._cached_incoming_open = []
    node._cached_outgoing_pending = []
    node._cached_outgoing_not_closed = []
    node._cached_address_to_open_channel = {}

    all_channels = [
        build_channel(node.address.native, "peer_a", "Open"),
        build_channel(node.address.native, "peer_b", "Closed"),
        build_channel("peer_c", node.address.native, "Open"),
        build_channel("peer_d", "peer_e", "Open"),
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

    await node.retrieve_channels()

    assert [channel.destination for channel in node.channels.outgoing] == ["peer_a"]
    assert [channel.source for channel in node.channels.incoming] == ["peer_c"]
    assert node.outgoing_channel_balances == topology
    assert node.network_state.outgoing_channel_balances == topology
    assert node._cached_outgoing_open is None
    assert node._cached_incoming_open is None
    assert node._cached_outgoing_pending is None
    assert node._cached_outgoing_not_closed is None
    assert node._cached_address_to_open_channel is None


@pytest.mark.asyncio
async def test_fund_channels_schedules_only_low_balance_known_peer_channels(node: Node, mocker):
    node.peers = {"peer_low": Peer("peer_low"), "peer_other": Peer("peer_other")}
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel(node.address.native, "peer_low", balance="0.01 wxHOPR"),
        build_channel(node.address.native, "peer_unknown", balance="0.01 wxHOPR"),
        build_channel(node.address.native, "peer_other", balance="5 wxHOPR"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    fund_mock = mocker.patch.object(NodeHelper, "fund_channel", new=AsyncMock())
    lifecycle_request = mocker.patch.object(node.channel_lifecycle_coordinator, "request")
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await node.fund_channels()

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == "_execute"
    assert args == ()
    assert kwargs == {"publish_to_task_set": False}
    await callback()
    fund_mock.assert_awaited_once_with(
        node.api,
        "peer_low",
        node.params.channel.funding_amount,
    )
    lifecycle_request.assert_called_once_with("fund_channel")


@pytest.mark.asyncio
async def test_close_old_channels_tracks_new_peers_and_closes_only_stale_channels(
    node: Node, mocker
):
    stale_time = datetime.now() - timedelta(seconds=node.params.channel.max_age.value + 5)
    recent_time = datetime.now() - timedelta(seconds=node.params.channel.max_age.value / 2)

    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel(node.address.native, "peer_stale"),
        build_channel(node.address.native, "peer_recent"),
        build_channel(node.address.native, "peer_new"),
    ]
    node.channels.incoming = []
    node.peer_history = {"peer_stale": stale_time, "peer_recent": recent_time}
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    close_mock = mocker.patch.object(NodeHelper, "close_channel", new=AsyncMock())
    lifecycle_request = mocker.patch.object(node.channel_lifecycle_coordinator, "request")
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await node.close_old_channels()

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == "_execute"
    assert args == ()
    assert kwargs == {"publish_to_task_set": False}
    await callback()
    close_mock.assert_awaited_once_with(node.api, "peer_stale", "old_closed")
    lifecycle_request.assert_called_once_with("close_old_channel")
    assert "peer_new" in node.peer_history
    assert node.peer_history["peer_new"] >= stale_time


@pytest.mark.asyncio
async def test_close_pending_channels_schedules_pending_only(node: Node, mocker):
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel(node.address.native, "peer_pending", "PendingToClose"),
        build_channel(node.address.native, "peer_open", "Open"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await node.close_pending_channels()

    assert len(scheduled) == 1
    assert scheduled[0][0].__name__ == "_reclose"


@pytest.mark.asyncio
async def test_close_incoming_channels_schedules_all_incoming_open(node: Node, mocker):
    node.channels = Channels({})
    node.channels.outgoing = []
    node.channels.incoming = [
        build_channel("peer_a", node.address.native, "Open"),
        build_channel("peer_b", node.address.native, "Open"),
    ]
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    close_mock = mocker.patch.object(NodeHelper, "close_channel", new=AsyncMock())
    lifecycle_request = mocker.patch.object(node.channel_lifecycle_coordinator, "request")
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await node.close_incoming_channels()

    assert [item[0].__name__ for item in scheduled] == ["_execute", "_execute"]
    for callback, _args, _kwargs in scheduled:
        await callback()
    assert close_mock.await_count == 2
    close_mock.assert_any_await(node.api, node.address.native, "incoming_closed")
    assert lifecycle_request.call_count == 2


@pytest.mark.asyncio
async def test_open_channels_skips_peers_with_open_or_pending_channels(node: Node, mocker):
    node.peers = {
        "peer_open": Peer("peer_open"),
        "peer_pending": Peer("peer_pending"),
        "peer_missing": Peer("peer_missing"),
    }
    node.channels = Channels({})
    node.channels.outgoing = [
        build_channel(node.address.native, "peer_open", "Open"),
        build_channel(node.address.native, "peer_pending", "PendingToClose"),
    ]
    node.channels.incoming = []
    node.invalidate_channel_cache()

    scheduled: list[tuple] = []
    open_mock = mocker.patch.object(NodeHelper, "open_channel", new=AsyncMock())
    lifecycle_request = mocker.patch.object(node.channel_lifecycle_coordinator, "request")
    mocker.patch(
        "core.mixins.channel.actions.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append((callback, args, kwargs)),
    )

    await node.open_channels()

    assert len(scheduled) == 1
    callback, args, kwargs = scheduled[0]
    assert callback.__name__ == "_execute"
    assert args == ()
    assert kwargs == {"publish_to_task_set": False}
    await callback()
    open_mock.assert_awaited_once_with(
        node.api,
        "peer_missing",
        node.params.channel.funding_amount,
    )
    lifecycle_request.assert_called_once_with("open_channel")
