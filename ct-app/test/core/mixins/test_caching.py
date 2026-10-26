"""
Test suite caching optimizations.

Tests cover:
- Peer address caching and invalidation
- Channel filtering caching and invalidation
- Reachable destinations caching
- Session destination selection with caching
"""

import pytest

from core.api.response_objects import ConnectedPeer
from core.types.message_format import MessageFormat
from core.node import Node


class TestPeerAddressCaching:
    """Test peer address caching optimization in SessionMixin."""

    @pytest.mark.asyncio
    async def test_peer_addresses_property_returns_correct_set(self, node: Node):
        """Test that peer_addresses property returns correct set of addresses."""
        await node.retrieve_peers()

        peer_addresses = node.peer_addresses
        expected_addresses = set(node.peers.keys())

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
    async def test_address_to_open_channel_returns_correct_dict(self, node: Node):
        """Test that address_to_open_channel property returns correct dict mapping."""
        await node.rebuild_channel_views()

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
        await node.rebuild_channel_views()

        # First access populates the cache
        first_by_address = node.address_to_open_channel

        # Second access should return the same cached object
        assert node.address_to_open_channel is first_by_address

    @pytest.mark.asyncio
    async def test_channel_cache_invalidation_on_retrieve(self, node: Node, mocker):
        """Test that channel caches are invalidated when channels are retrieved."""
        await node.rebuild_channel_views()

        # Populate the cache
        _ = node.address_to_open_channel
        assert node._cached_address_to_open_channel is not None

        # Retrieve channels again
        await node.rebuild_channel_views()

        # The cache should be invalidated
        assert node._cached_address_to_open_channel is None


class TestReachableDestinationsCaching:
    """Test reachable destinations caching optimization in SessionMixin."""

    @pytest.mark.asyncio
    async def test_reachable_destinations_property_returns_correct_set(self, node: Node):
        """Test that reachable_destinations returns correct intersection."""
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2", "address_3", "address_unknown"]

        reachable = node.reachable_destinations
        peer_addresses = set(node.peers.keys())
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

    @pytest.mark.asyncio
    async def test_session_destinations_assignment_invalidates_reachable_cache(self, node: Node):
        await node.retrieve_peers()
        node.session_destinations = ["address_1", "address_2"]

        original = node.reachable_destinations
        assert node._cached_reachable_destinations is original

        node.session_destinations = ["address_3", "address_4"]

        assert node._cached_reachable_destinations is None
        assert node.reachable_destinations != original


class TestSessionDestinationSelection:
    """Test session destination selection with caching optimizations."""

    @pytest.mark.asyncio
    async def test_select_destination_uses_cached_properties(self, node: Node):
        """Test that _select_session_destination uses cached reachable_destinations."""
        await node.retrieve_peers()
        await node.rebuild_channel_views()

        node.session_destinations = ["address_1", "address_2", "address_3"]

        # Populate cache by accessing property
        _ = node.reachable_destinations
        assert node._cached_reachable_destinations is not None

        # Create mock message
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
        await node.rebuild_channel_views()

        node.session_destinations = ["address_1", "address_2", "address_3", "address_4"]

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
