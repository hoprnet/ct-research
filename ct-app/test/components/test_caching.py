"""
Test suite for Phase 1 caching optimizations.

Tests cover:
- Peer address caching and invalidation
- Channel filtering caching and invalidation
- Reachable destinations caching
- Session destination selection with caching
"""

import pytest

from core.api.response_objects import Channel, Channels, ConnectedPeer
from core.components import Peer
from core.node import Node


class TestPeerAddressCaching:
    """Test peer address caching optimization in SessionMixin."""

    @pytest.mark.asyncio
    async def test_peer_addresses_property_returns_correct_set(self, node: Node):
        """Test that peer_addresses property returns correct set of addresses."""
        await node.retrieve_peers()

        peer_addresses = node.peer_addresses
        expected_addresses = {peer.address.native for peer in node.peers}

        assert peer_addresses == expected_addresses
        assert isinstance(peer_addresses, set)

    @pytest.mark.asyncio
    async def test_peer_addresses_cache_is_populated_on_first_access(self, node: Node):
        """Test that cache is None initially and populated on first access."""
        await node.retrieve_peers()

        # Cache should be None before first access
        assert node._cached_peer_addresses is None

        # Access property to populate cache
        _ = node.peer_addresses

        # Cache should now be populated
        assert node._cached_peer_addresses is not None
        assert len(node._cached_peer_addresses) == len(node.peers)

    @pytest.mark.asyncio
    async def test_peer_addresses_cache_is_reused(self, node: Node):
        """Test that cached value is reused on subsequent accesses."""
        await node.retrieve_peers()

        # First access populates cache
        first_access = node.peer_addresses
        cached_value = node._cached_peer_addresses

        # Second access should return same cached object
        second_access = node.peer_addresses

        assert first_access is cached_value
        assert second_access is cached_value
        assert id(first_access) == id(second_access)

    @pytest.mark.asyncio
    async def test_peer_cache_invalidation_works(self, node: Node):
        """Test that invalidate_peer_cache() clears the cache."""
        await node.retrieve_peers()

        # Populate cache
        _ = node.peer_addresses
        assert node._cached_peer_addresses is not None

        # Invalidate cache
        node.invalidate_peer_cache()

        # Cache should be None
        assert node._cached_peer_addresses is None

    @pytest.mark.asyncio
    async def test_peer_cache_invalidation_on_new_peer(self, node: Node, mocker):
        """Test that cache is invalidated when new peers are added."""
        await node.retrieve_peers()

        # Populate cache
        original_addresses = node.peer_addresses
        assert node._cached_peer_addresses is not None

        # Mock API to return additional peer
        new_peers = [ConnectedPeer({"address": f"address_{i}"}) for i in range(6)]
        mocker.patch.object(node.api, "peers", return_value=new_peers)

        # Retrieve peers again (should add new peer)
        await node.retrieve_peers()

        # Cache should be invalidated (set to None by invalidate_peer_cache)
        # Note: We check that new data is different, not that cache was explicitly None
        new_addresses = node.peer_addresses
        assert len(new_addresses) > len(original_addresses)

    @pytest.mark.asyncio
    async def test_reachable_destinations_invalidation(self, node: Node):
        """Test that reachable_destinations cache is invalidated with peer cache."""
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2", "address_3"]

        # Populate both caches
        _ = node.peer_addresses
        _ = node.reachable_destinations

        assert node._cached_peer_addresses is not None
        assert node._cached_reachable_destinations is not None

        # Invalidate peer cache
        node.invalidate_peer_cache()

        # Both caches should be None
        assert node._cached_peer_addresses is None
        assert node._cached_reachable_destinations is None


class TestChannelCaching:
    """Test channel caching optimization in ChannelMixin."""

    @pytest.mark.asyncio
    async def test_outgoing_open_channels_returns_correct_list(self, node: Node):
        """Test that outgoing_open_channels property returns correct filtered list."""
        await node.retrieve_channels()

        cached_channels = node.outgoing_open_channels
        expected_channels = [c for c in node.channels.outgoing if c.status.is_open]

        assert len(cached_channels) == len(expected_channels)
        assert all(c.status.is_open for c in cached_channels)

    @pytest.mark.asyncio
    async def test_incoming_open_channels_returns_correct_list(self, node: Node):
        """Test that incoming_open_channels property returns correct filtered list."""
        await node.retrieve_channels()

        cached_channels = node.incoming_open_channels
        expected_channels = [c for c in node.channels.incoming if c.status.is_open]

        assert len(cached_channels) == len(expected_channels)
        assert all(c.status.is_open for c in cached_channels)

    @pytest.mark.asyncio
    async def test_outgoing_pending_channels_returns_correct_list(self, node: Node, mocker):
        """Test that outgoing_pending_channels property returns correct filtered list."""
        # Create channels with pending status
        pending_channels = [
            Channel(
                {
                    "balance": "1 wxHOPR",
                    "id": "channel_pending",
                    "destination": "dest_1",
                    "source": "address_0",
                    "status": "PendingToClose",
                }
            )
        ]

        channels = Channels({})
        channels.all = pending_channels
        channels.outgoing = pending_channels
        channels.incoming = []

        mocker.patch.object(node.api, "channels", return_value=channels)
        await node.retrieve_channels()

        cached_channels = node.outgoing_pending_channels

        assert len(cached_channels) == 1
        assert all(c.status.is_pending for c in cached_channels)

    @pytest.mark.asyncio
    async def test_outgoing_not_closed_channels_returns_correct_list(self, node: Node):
        """Test that outgoing_not_closed_channels property returns correct filtered list."""
        await node.retrieve_channels()

        cached_channels = node.outgoing_not_closed_channels
        expected_channels = [c for c in node.channels.outgoing if not c.status.is_closed]

        assert len(cached_channels) == len(expected_channels)
        assert all(not c.status.is_closed for c in cached_channels)

    @pytest.mark.asyncio
    async def test_address_to_open_channel_returns_correct_dict(self, node: Node):
        """Test that address_to_open_channel property returns correct dict mapping."""
        await node.retrieve_channels()

        cached_dict = node.address_to_open_channel
        expected_dict = {c.destination: c for c in node.channels.outgoing if c.status.is_open}

        assert len(cached_dict) == len(expected_dict)
        assert all(c.status.is_open for c in cached_dict.values())

        # Verify mapping correctness
        for address, channel in cached_dict.items():
            assert channel.destination == address

    @pytest.mark.asyncio
    async def test_channel_caches_are_reused(self, node: Node):
        """Test that cached channel values are reused on subsequent accesses."""
        await node.retrieve_channels()

        # First access populates caches
        first_outgoing = node.outgoing_open_channels
        first_incoming = node.incoming_open_channels

        # Second access should return same cached objects
        second_outgoing = node.outgoing_open_channels
        second_incoming = node.incoming_open_channels

        assert first_outgoing is second_outgoing
        assert first_incoming is second_incoming

    @pytest.mark.asyncio
    async def test_channel_cache_invalidation_on_retrieve(self, node: Node, mocker):
        """Test that channel caches are invalidated when channels are retrieved."""
        await node.retrieve_channels()

        # Populate all caches
        _ = node.outgoing_open_channels
        _ = node.incoming_open_channels
        _ = node.outgoing_pending_channels
        _ = node.outgoing_not_closed_channels
        _ = node.address_to_open_channel

        # All caches should be populated
        assert node._cached_outgoing_open is not None
        assert node._cached_incoming_open is not None

        # Retrieve channels again
        await node.retrieve_channels()

        # All caches should be invalidated
        assert node._cached_outgoing_open is None
        assert node._cached_incoming_open is None
        assert node._cached_outgoing_pending is None
        assert node._cached_outgoing_not_closed is None
        assert node._cached_address_to_open_channel is None


class TestReachableDestinationsCaching:
    """Test reachable destinations caching optimization in SessionMixin."""

    @pytest.mark.asyncio
    async def test_reachable_destinations_property_returns_correct_set(self, node: Node):
        """Test that reachable_destinations returns correct intersection."""
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2", "address_3", "address_unknown"]

        reachable = node.reachable_destinations
        peer_addresses = {peer.address.native for peer in node.peers}
        expected = set(node.session_destinations) & peer_addresses

        assert reachable == expected
        assert "address_unknown" not in reachable

    @pytest.mark.asyncio
    async def test_reachable_destinations_cache_is_populated(self, node: Node):
        """Test that cache is None initially and populated on first access."""
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2"]

        # Cache should be None before first access
        assert node._cached_reachable_destinations is None

        # Access property to populate cache
        _ = node.reachable_destinations

        # Cache should now be populated
        assert node._cached_reachable_destinations is not None

    @pytest.mark.asyncio
    async def test_reachable_destinations_cache_is_reused(self, node: Node):
        """Test that cached value is reused on subsequent accesses."""
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2"]

        # First access populates cache
        first_access = node.reachable_destinations
        cached_value = node._cached_reachable_destinations

        # Second access should return same cached object
        second_access = node.reachable_destinations

        assert first_access is cached_value
        assert second_access is cached_value


class TestSessionDestinationSelection:
    """Test session destination selection with caching optimizations."""

    @pytest.mark.asyncio
    async def test_select_destination_uses_cached_properties(self, node: Node):
        """Test that _select_session_destination uses cached reachable_destinations."""
        await node.retrieve_peers()
        await node.retrieve_channels()

        node.session_destinations = ["address_1", "address_2", "address_3"]

        # Populate cache by accessing property
        _ = node.reachable_destinations
        assert node._cached_reachable_destinations is not None

        # Create mock message
        from core.components.messages import MessageFormat

        message = MessageFormat("address_1", batch_size=3)

        channels = [c.destination for c in node.channels.outgoing]

        # Call destination selection
        selected = node._select_session_destination(message, channels)

        # Should have used cached property (cache still populated)
        assert node._cached_reachable_destinations is not None

        # Selected destination should be from reachable set
        if selected:  # May be None if no valid destinations
            assert selected in node.reachable_destinations

    @pytest.mark.asyncio
    async def test_select_destination_filters_relayer_correctly(self, node: Node):
        """Test that destination selection correctly filters out the relayer."""
        await node.retrieve_peers()
        await node.retrieve_channels()

        node.session_destinations = ["address_1", "address_2", "address_3", "address_4"]

        from core.components.messages import MessageFormat

        relayer = "address_2"
        message = MessageFormat(relayer, batch_size=3)

        channels = [c.destination for c in node.channels.outgoing]

        # Call destination selection multiple times
        destinations = set()
        for _ in range(20):  # Multiple iterations to test randomness
            selected = node._select_session_destination(message, channels)
            if selected:
                destinations.add(selected)

        # Relayer should never be selected
        assert relayer not in destinations

        # All selected destinations should be reachable
        for dest in destinations:
            assert dest in node.reachable_destinations


class TestMergeDataSourcesOptimization:
    """Test mergeDataSources optimization with indexed lookups."""

    @pytest.mark.asyncio
    async def test_mergeDataSources_with_large_dataset(self):
        """Test mergeDataSources performance with large dataset (100+ peers)."""
        from core.components import Utils
        from core.components.balance import Balance
        from core.rpc import entries as rpc_entries
        from core.subgraph import entries as sg_entries

        # Create large dataset
        num_peers = 100
        num_nodes = 100
        num_allocations = 50

        topology_list = {f"address_{i}": Balance("1 wxHOPR") for i in range(num_peers)}
        peers_list = [Peer(f"address_{i}") for i in range(num_peers)]
        nodes_list = [
            sg_entries.Node(
                f"address_{i}", sg_entries.Safe(f"safe_{i}", "10", f"{i}", [f"owner_{i}"])
            )
            for i in range(num_nodes)
        ]
        allocation_list = [
            rpc_entries.Allocation(
                f"owner_{i}", "schedule", Balance(f"{i * 10} wxHOPR"), Balance.zero("wxHOPR")
            )
            for i in range(num_allocations)
        ]

        # Link allocations to safes
        for i, allocation in enumerate(allocation_list):
            # Each allocation links to 2-3 safes
            allocation.linked_safes = {f"safe_{i}", f"safe_{(i+1) % num_nodes}"}

        # Run mergeDataSources
        await Utils.mergeDataSources(topology_list, peers_list, nodes_list, allocation_list, {})

        # Verify results
        peers_with_safe = [p for p in peers_list if p.safe is not None]
        assert len(peers_with_safe) == num_peers

        # Verify balances were calculated
        for peer in peers_with_safe:
            assert peer.safe.additional_balance is not None

    @pytest.mark.asyncio
    async def test_mergeDataSources_indexed_lookups(self):
        """Test that mergeDataSources uses indexed lookups correctly."""
        from core.components import Utils
        from core.components.balance import Balance
        from core.rpc import entries as rpc_entries
        from core.subgraph import entries as sg_entries

        # Create test data with specific structure to verify indexing
        topology_list = {"ADDRESS_1": Balance("1 wxHOPR")}  # Mixed case
        peers_list = [Peer("ADDRESS_1")]
        nodes_list = [
            sg_entries.Node(
                "address_1",  # Lowercase - tests case-insensitive lookup
                sg_entries.Safe("safe_1", "10", "1", ["owner_1"]),
            )
        ]
        allocation_list = [
            rpc_entries.Allocation(
                "owner_1", "schedule", Balance("100 wxHOPR"), Balance.zero("wxHOPR")
            )
        ]
        allocation_list[0].linked_safes = {"safe_1"}

        # Run mergeDataSources
        await Utils.mergeDataSources(topology_list, peers_list, nodes_list, allocation_list, {})

        # Verify indexed lookup worked with case-insensitive matching
        assert peers_list[0].safe is not None
        assert peers_list[0].safe.address == "safe_1"
        assert peers_list[0].safe.additional_balance == Balance("100 wxHOPR")

    @pytest.mark.asyncio
    async def test_mergeDataSources_edge_cases(self):
        """Test mergeDataSources handles edge cases correctly."""
        from core.components import Utils

        # Test with empty lists
        await Utils.mergeDataSources({}, [], [], [], {})

        # Test with None values
        peers_list = [Peer("address_1")]
        await Utils.mergeDataSources({}, peers_list, [], [], {})

        # Peer should not have safe set
        assert peers_list[0].safe is None
