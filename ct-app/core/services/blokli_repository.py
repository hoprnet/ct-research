import logging
from collections.abc import Callable
from typing import AsyncIterator, Protocol

from ..blokli.adapters import to_channel, to_node_ip
from ..blokli.entries import BlokliTicketParameters
from ..blokli.providers import (
    ChannelGraphSubscription,
    NodeAddressesSubscription,
    TicketParametersSubscription,
)
from ..types.network_models import ChannelGraphUpdate, NodeAddressUpdate

logger = logging.getLogger(__name__)


class NetworkRepository(Protocol):
    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]: ...
    def stream_channel_graph(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[ChannelGraphUpdate]: ...
    def stream_node_addresses(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[NodeAddressUpdate]: ...


class GraphqlNetworkRepository:
    def __init__(self, url: str, token: str | None = None):
        self.url = url
        self.token = token

    def stream_ticket_parameters(self) -> AsyncIterator[BlokliTicketParameters]:
        async def _stream() -> AsyncIterator[BlokliTicketParameters]:
            async with TicketParametersSubscription(self.url, self.token) as client:
                async for params in client.subscribe():
                    logger.debug(
                        "Ticket parameters subscription event",
                        {
                            "ticket_price": params.ticket_price.as_str,
                            "min_ticket_winning_probability": params.min_ticket_winning_probability,
                        },
                    )
                    yield params

        return _stream()

    def stream_channel_graph(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[ChannelGraphUpdate]:
        """
        Streams the network's non-closed channels: a full snapshot on every (re)connection,
        then each change. A channel reported as closed must be dropped.
        """

        async def _stream() -> AsyncIterator[ChannelGraphUpdate]:
            async with ChannelGraphSubscription(self.url, self.token) as client:
                async for entry in client.subscribe(on_connect=on_connect):
                    channel = to_channel(entry)
                    if channel is None:
                        logger.debug("Dropping incomplete channel graph entry")
                        continue
                    yield ChannelGraphUpdate(channel_id=entry.channel_id, channel=channel)

        return _stream()

    def stream_node_addresses(
        self, on_connect: Callable[[], None] | None = None
    ) -> AsyncIterator[NodeAddressUpdate]:
        """
        Streams each node's announced host (an IP or a DNS name, not resolved): a full snapshot
        on every (re)connection, then each change. Nodes not resent after a reconnection are
        swept by the consumer.
        """

        async def _stream() -> AsyncIterator[NodeAddressUpdate]:
            async with NodeAddressesSubscription(self.url, self.token) as client:
                async for entry in client.subscribe(on_connect=on_connect):
                    pair = to_node_ip(entry)
                    if pair is None:
                        logger.debug("Dropping account entry without a usable announced address")
                        continue
                    address, ip = pair
                    yield NodeAddressUpdate(address=address, ip=ip)

        return _stream()
