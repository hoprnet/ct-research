from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channel, Channels, Session, TicketPrice
from ..config_parser.parameters import Parameters
from ..services.blokli_repository import NetworkRepository
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
    running: bool
    connected: bool

    blokli_repository: NetworkRepository
    network_state_service: NetworkStateService
    network_sync_orchestrator: NetworkSyncOrchestrator

    _cached_peer_addresses: set[str] | None
    _cached_reachable_destinations: set[str] | None
    _cached_outgoing_open: list[Channel] | None
    _cached_incoming_open: list[Channel] | None
    _cached_outgoing_pending: list[Channel] | None
    _cached_outgoing_not_closed: list[Channel] | None
    _cached_address_to_open_channel: dict[str, Channel] | None

    @property
    def address_to_open_channel(self) -> dict[str, Channel]: ...
