import asyncio

import pytest

from core.node import Node
from core.services.node_address_store import NodeAddressStore
from core.types.network_models import NodeAddressUpdate


@pytest.mark.asyncio
async def test_apply_node_address_update_stores_ip_and_requests_refresh(node: Node, mocker):
    request = mocker.patch.object(node.network_update_coordinator, "request")

    node.apply_node_address_update(NodeAddressUpdate(address="0xa", ip="1.2.3.4"))

    assert node.node_address_store.ip_for("0xa") == "1.2.3.4"
    request.assert_called_once()


@pytest.mark.asyncio
async def test_subscribe_node_addresses_starts_generation_and_sweeps(node: Node, mocker):
    node.node_address_store = NodeAddressStore()
    mocker.patch.object(node.network_update_coordinator, "request")
    scheduled: list = []
    mocker.patch(
        "core.mixins.peers_discovery.AsyncLoop.add",
        side_effect=lambda callback, *args, **kwargs: scheduled.append(callback),
    )

    def stream_node_addresses(on_connect=None):
        async def _stream():
            assert on_connect is not None, "the subscription should pass a connect hook"
            on_connect()
            yield NodeAddressUpdate(address="0xa", ip="1.1.1.1")
            yield NodeAddressUpdate(address="0xb", ip="2.2.2.2")
            raise asyncio.CancelledError

        return _stream()

    mocker.patch.object(
        node.blokli_repository, "stream_node_addresses", side_effect=stream_node_addresses
    )

    with pytest.raises(asyncio.CancelledError):
        await node.subscribe_node_addresses()

    assert node.node_address_store.ip_for("0xa") == "1.1.1.1"
    assert node.node_address_store.ip_for("0xb") == "2.2.2.2"
    assert [callback.__name__ for callback in scheduled] == ["_sweep"]
