from __future__ import annotations

import asyncio
from typing import Optional

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channel, Channels, Session, TicketPrice
from ..config_parser.parameters import Parameters
from ..services.blokli_repository import NetworkRepository
from ..services.channel_graph_store import ChannelGraphStore
from ..services.channel_view_coordinator import ChannelViewCoordinator
from ..services.burst_plan import RelayedCostTracker
from ..services.eligibility_refresh_coordinator import EligibilityRefreshCoordinator
from ..services.network_update_coordinator import NetworkUpdateCoordinator
from ..services.session_lifecycle_coordinator import SessionLifecycleCoordinator
from ..services.shutdown_coordinator import ShutdownCoordinator
from ..types.address import Address
from ..types.balance import Balance
from ..types.peer import Peer
from ..types.session_rate_limiter import SessionRateLimiter


class NodeRuntimeState:
    api: HoprdAPI
    url: str
    address: Optional[Address]

    params: Parameters
    ticket_price: Optional[TicketPrice]
    min_ticket_winning_probability: Optional[float]

    channels: Optional[Channels]
    channel_graph: ChannelGraphStore
    channel_view_coordinator: ChannelViewCoordinator
    _channel_graph_sweep_task: Optional[asyncio.Task[None]]
    outgoing_channel_balances: dict[str, Balance]

    peers: dict[str, Peer]
    eligible_relayers: set[str]

    sessions: dict[str, Session]
    session_destinations: list[str]
    session_close_grace_period: dict[str, float]
    session_rate_limiter: SessionRateLimiter
    _pending_session_creations: dict[str, asyncio.Task[Optional[Session]]]
    _in_flight_message_tasks: set[asyncio.Task]
    _in_flight_tasks_by_session_port: dict[int, set[asyncio.Task]]
    _session_retry_wait_seconds: dict[str, float]
    _pending_requeue_tasks: set[asyncio.Task[None]]
    _session_retry_log_state: dict[tuple[str, str], tuple[float, int]]
    eligibility_refresh_coordinator: EligibilityRefreshCoordinator
    relayed_cost_tracker: RelayedCostTracker
    running: bool
    connected: bool

    blokli_repository: NetworkRepository
    network_update_coordinator: NetworkUpdateCoordinator
    session_lifecycle_coordinator: SessionLifecycleCoordinator
    shutdown_coordinator: ShutdownCoordinator

    _cached_peer_addresses: set[str] | None
    _cached_reachable_destinations: set[str] | None
    _cached_address_to_open_channel: dict[str, Channel] | None

    @property
    def address_to_open_channel(self) -> dict[str, Channel]: ...
