"""
Node - Main controller for HOPR network node operations.

This module provides the Node class which manages the complete lifecycle of a HOPR node,
including:
- Session management with grace periods and parallel cleanup
- Peer discovery and channel management
- Balance and economic model tracking
- Network topology and blokli data

Session Management:
    Sessions are WebSocket connections to other nodes for message relay. The node implements
    a grace period mechanism (60 seconds) before closing sessions when peers become
    unreachable, preventing premature closures during temporary network issues.

Thread Safety:
    Session operations use a lock-free design leveraging asyncio's single-threaded event
    loop. Dictionary snapshots are used to avoid modification during iteration.
"""

import asyncio
import logging
from datetime import datetime
from collections.abc import Sequence
from typing import Optional

from api_lib.headers.authorization import Bearer
from prometheus_client import Gauge

from .mixins import ChannelMixin, EconomicSystemMixin, PeersMixin, SessionMixin, StateMixin
from .api.hoprd_api import HoprdAPI
from .api.response_objects import Channel, Channels, Session, TicketPrice
from .types.address import Address
from .types.asyncloop import AsyncLoop
from .types.balance import Balance
from .config_parser import Parameters
from .components.node_helper import NodeHelper
from .types.peer import Peer
from .types.network_state import NetworkState
from .types.session_rate_limiter import SessionRateLimiter
from .components.decorators import get_keepalive_methods
from .services.node_runtime_factory import NodeRuntimeFactory
from .services.economic_model_refresh_coordinator import EconomicModelRefreshCoordinator
from .services.channel_lifecycle_coordinator import ChannelLifecycleCoordinator
from .services.network_update_coordinator import NetworkUpdateCoordinator
from .services.send_plan_coordinator import SendPlanCoordinator
from .services.session_lifecycle_coordinator import SessionLifecycleCoordinator
from .services.shutdown_coordinator import ShutdownCoordinator

BALANCE_MULTIPLIER = Gauge("ct_balance_multiplier", "factor to multiply the balance by")

logger = logging.getLogger(__name__)


class Node(
    ChannelMixin,
    EconomicSystemMixin,
    PeersMixin,
    SessionMixin,
    StateMixin,
):
    def __init__(self, url: str, key: str, params: Parameters):
        """
        Create a new Node with the specified url and key.

        Initializes all state tracking for the node including session management,
        peer connections, and economic model data.

        Session State Attributes:
            sessions (dict[str, Session]): Active sessions indexed by relayer address.
                Thread-safe via asyncio single-threaded event loop.
            session_close_grace_period (dict[str, float]): Tracks when grace period
                started for each unreachable peer. Timestamp is in seconds since epoch.
            session_destinations (list[str]): List of peer addresses eligible for
                session creation.

        Args:
            url: The URL of the HOPR node API (e.g., "http://localhost:3001")
            key: Authentication key for the node API
            params: Configuration parameters. Defaults to Parameters() if not provided.

        Note:
            The node is initialized in a disconnected state (connected=False, running=True).
            Call start() to begin keepalive loops and connect to the network.
        """
        self.api = HoprdAPI(url, Bearer(key), "/api/v4")
        self.url = url

        self.peers = dict[str, Peer]()
        self.peer_history = dict[str, datetime]()
        self.network_state = NetworkState()
        self._session_destinations = list[str]()
        self.sessions = dict[str, Session]()
        # relayer -> timestamp when grace period started
        self.session_close_grace_period = dict[str, float]()
        self._in_flight_message_tasks = set[asyncio.Task]()
        self._in_flight_tasks_by_session_port = dict[int, set[asyncio.Task]]()
        self._pending_session_creations = dict[str, asyncio.Task[Optional[Session]]]()

        # Initialize params first so we can use session configuration
        self.params = params

        NodeRuntimeFactory.configure_runtime(self, self.params)

        # Session rate limiter to prevent API overload from failed attempts
        # Use default values if sessions config is not available
        base_delay = self.params.sessions.session_retry_base_delay.value
        max_delay = self.params.sessions.session_retry_max_delay.value

        self.session_rate_limiter = SessionRateLimiter(
            base_delay=base_delay,
            max_delay=max_delay,
        )

        self.address: Optional[Address] = None
        self.channels: Optional[Channels] = None

        self.outgoing_channel_balances = dict[str, Balance]()
        self.ticket_price: Optional[TicketPrice] = None
        self.min_ticket_winning_probability: Optional[float] = None
        self.economic_model_refresh_coordinator = EconomicModelRefreshCoordinator(
            self._apply_economic_model_once
        )
        self.channel_lifecycle_coordinator = ChannelLifecycleCoordinator(
            self.reconcile_channels_once
        )
        self.network_update_coordinator = NetworkUpdateCoordinator(
            self.reconcile_peer_allocations,
            self.trigger_economic_model_refresh,
        )
        self.send_plan_coordinator = SendPlanCoordinator()
        self.session_lifecycle_coordinator = SessionLifecycleCoordinator()
        self.shutdown_coordinator = ShutdownCoordinator()
        self.shutdown_coordinator.register_async(
            "economic_model_refresh_coordinator",
            self.economic_model_refresh_coordinator.close,
        )
        self.shutdown_coordinator.register_async(
            "network_update_coordinator",
            self.network_update_coordinator.close,
        )
        self.shutdown_coordinator.register_async(
            "channel_lifecycle_coordinator",
            self.channel_lifecycle_coordinator.close,
        )
        self.shutdown_coordinator.register_async(
            "channel_reclose_tasks",
            self.close_channel_reclose_tasks,
        )

        self.connected = False
        self.running = True

        # Initialize caching attributes
        # Peer address caching (SessionMixin)
        self._cached_peer_addresses: set[str] | None = None
        self._cached_reachable_destinations: set[str] | None = None

        # Channel caching (ChannelMixin)
        self._cached_outgoing_open: list[Channel] | None = None
        self._cached_incoming_open: list[Channel] | None = None
        self._cached_outgoing_pending: list[Channel] | None = None
        self._cached_outgoing_not_closed: list[Channel] | None = None
        self._cached_address_to_open_channel: dict[str, Channel] | None = None
        self._pending_channel_reclose_tasks = dict[str, asyncio.Task[None]]()

        BALANCE_MULTIPLIER.set(1.0)

    @property
    def session_destinations(self) -> list[str]:
        return self._session_destinations

    @session_destinations.setter
    def session_destinations(self, destinations: Sequence[str]) -> None:
        self._session_destinations = list(destinations)
        self._cached_reachable_destinations = None

    async def start(self):
        await self.retrieve_address()

        logger.info(
            "Scheduling subscription methods",
            {"methods": ["subscribe_accounts", "ticket_parameters"]},
        )
        AsyncLoop.add(self.subscribe_accounts)
        AsyncLoop.add(self.ticket_parameters)
        self.channel_lifecycle_coordinator.request("startup")

        keepalive_methods = get_keepalive_methods(self)
        logger.info(
            "Scheduling keepalive methods",
            {
                "count": len(keepalive_methods),
                "methods": [method.__name__ for method in keepalive_methods],
            },
        )
        AsyncLoop.update(keepalive_methods)

        await AsyncLoop.gather()

    async def stop(self):
        """
        Gracefully stop the node and clean up all resources.

        Implements a three-phase parallel shutdown strategy for optimal performance:

        Phase 1 - Parallel API Close:
            Closes all sessions at the API level concurrently using asyncio.gather().
            This is the slowest operation (network I/O), so parallelization provides
            significant speedup. For 200 sessions, this reduces shutdown time from
            ~20 seconds (sequential) to <1 second (parallel).

        Phase 2 - Sequential Socket Close:
            Closes all socket connections synchronously. These are fast operations
            (local system calls), so parallelization overhead outweighs benefits.

        Phase 3 - Cache Cleanup:
            Clears all session-related dictionaries to free memory and ensure
            clean state for potential restart.

        Exception Handling:
            - API close failures are logged but don't stop the shutdown process
            - Socket close failures are logged but don't prevent cache cleanup
            - Uses return_exceptions=True to ensure all cleanup attempts complete

        Thread Safety:
            Uses snapshot pattern (list(self.sessions.items())) to avoid
            dictionary modification during iteration.

        Performance:
            With 200 sessions: ~100x faster than sequential (0.1s vs 20s)

        Example:
            >>> node = Node("http://localhost:3001", "my_key")
            >>> await node.start()
            >>> # ... node operations ...
            >>> await node.stop()  # Gracefully closes all sessions
        """
        self.running = False
        await self.shutdown_coordinator.run()
        await self.wait_for_in_flight_messages()

        # Close all active sessions
        # Create snapshot to avoid modification during iteration
        sessions_to_close = list(self.sessions.items())

        if not sessions_to_close:
            logger.info("Node stopped, no sessions to close")
            return

        # Phase 1: Close all sessions at API level in parallel
        async def close_session_safely(relayer: str, session):
            try:
                close_ok = await NodeHelper.close_session(self.api, session, relayer)
                if close_ok:
                    logger.debug("Closed session during shutdown", {"relayer": relayer})
                else:
                    logger.warning(
                        "Failed to close session during shutdown, preserving local state",
                        {"relayer": relayer, "port": session.port},
                    )
                return relayer, session, close_ok
            except Exception:
                logger.exception(
                    "Error closing session during shutdown, preserving local state",
                    {"relayer": relayer},
                )
                return relayer, session, False

        # Run all API close operations in parallel
        close_tasks = [
            close_session_safely(relayer, session) for relayer, session in sessions_to_close
        ]
        close_results = await asyncio.gather(*close_tasks, return_exceptions=True)

        successful_closes: list[tuple[str, Session]] = []
        for result in close_results:
            if isinstance(result, BaseException):
                logger.exception(
                    "Unexpected shutdown close failure result, preserving local state",
                    exc_info=result,
                )
                continue
            relayer, session, close_ok = result
            if close_ok:
                successful_closes.append((relayer, session))

        # Phase 2: Close sockets and clear cache only for successfully closed sessions
        for relayer, session in successful_closes:
            try:
                session.close_socket()
            except Exception:
                logger.exception("Error closing socket", {"relayer": relayer})

        for relayer, session in successful_closes:
            current_session = self.sessions.get(relayer)
            if current_session and current_session.port == session.port:
                self.sessions.pop(relayer, None)
                self.session_close_grace_period.pop(relayer, None)

        # Phase 3: Clear transient trackers
        self.session_rate_limiter.reset()
        self._in_flight_tasks_by_session_port.clear()
        self._in_flight_message_tasks.clear()
        if self.sessions:
            logger.warning(
                "Node stopped with unresolved sessions",
                {"session_count": len(self.sessions)},
            )
        else:
            logger.info(
                "Node stopped, all sessions closed",
                {"session_count": len(successful_closes)},
            )
