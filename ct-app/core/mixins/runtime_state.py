from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channel, Channels, Session, TicketPrice
from ..config_parser.parameters import Parameters
from ..services.blokli_repository import NetworkRepository
from ..services.channel_lifecycle_coordinator import ChannelLifecycleCoordinator
from ..services.economic_model_refresh_coordinator import EconomicModelRefreshCoordinator
from ..services.network_update_coordinator import NetworkUpdateCoordinator
from ..services.send_plan_coordinator import SendPlanCoordinator
from ..services.session_lifecycle_coordinator import SessionLifecycleCoordinator
from ..services.shutdown_coordinator import ShutdownCoordinator
from ..services.network_state_service import NetworkStateService
from ..services.network_sync_orchestrator import NetworkSyncOrchestrator
from ..types.address import Address
from ..types.balance import Balance
from ..types.network_state import NetworkState
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
    outgoing_channel_balances: dict[str, Balance]

    peers: dict[str, Peer]
    peer_history: dict[str, datetime]
    network_state: NetworkState

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
    economic_model_refresh_coordinator: EconomicModelRefreshCoordinator
    running: bool
    connected: bool

    blokli_repository: NetworkRepository
    network_state_service: NetworkStateService
    network_sync_orchestrator: NetworkSyncOrchestrator
    network_update_coordinator: NetworkUpdateCoordinator
    channel_lifecycle_coordinator: ChannelLifecycleCoordinator
    send_plan_coordinator: SendPlanCoordinator
    session_lifecycle_coordinator: SessionLifecycleCoordinator
    shutdown_coordinator: ShutdownCoordinator

    _cached_peer_addresses: set[str] | None
    _cached_reachable_destinations: set[str] | None
    _cached_outgoing_open: list[Channel] | None
    _cached_incoming_open: list[Channel] | None
    _cached_outgoing_pending: list[Channel] | None
    _cached_outgoing_not_closed: list[Channel] | None
    _cached_address_to_open_channel: dict[str, Channel] | None
    _pending_channel_reclose_tasks: dict[str, asyncio.Task[None]]

    @property
    def address_to_open_channel(self) -> dict[str, Channel]: ...
