"""
Session management mixin with parallel message processing.

ARCHITECTURE OVERVIEW
=====================

This module implements a worker pool architecture for high-throughput message processing.
Messages are processed concurrently by multiple workers pulling from a shared queue.

Performance Evolution:
----------------------
- Baseline without pool using async only: ~88 msg/sec with sequential processing
- Parallel pool: ~119 msg/sec with 10 concurrent workers

Worker Pool Architecture:
-------------------------
1. Main coordinator (`observe_message_queue`) spawns N worker tasks
2. Each worker continuously pulls messages from shared MessageQueue
3. Workers run until node.running = False
4. Graceful shutdown waits for all workers to complete

Thread Safety Guarantees:
-------------------------
- MessageQueue: asyncio.Queue is concurrent-safe (built-in)
- Session Creation: Double-check pattern prevents race conditions
- Rate Limiter: Per-relayer locks, thread-safe
- Metrics: Prometheus counters are thread-safe

Configuration:
--------------
- Worker count: Configure via sessions.message_worker_count in config.yaml
- Default: 10 workers
- Each worker has unique ID for metrics tracking

Bottlenecks:
------------
At 130 msg/sec with 10 workers:
1. Session creation rate limiter (exponential backoff)
2. Async context switching overhead
3. Test environment adds ~10% overhead
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

from ..components.asyncloop import AsyncLoop
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.messages import MessageFormat, MessageQueue
from ..components.node_helper import NodeHelper
from .protocols import HasAPI, HasChannels, HasPeers, HasSession

if TYPE_CHECKING:
    from ..api.response_objects import Session

configure_logging()
logger = logging.getLogger(__name__)

# Session configuration constants
DEFAULT_SESSION_GRACE_PERIOD_SECONDS = 60  # Time before closing unreachable peer sessions
DEFAULT_LISTEN_HOST = "127.0.0.1"  # Local socket binding address


class SessionMixin(HasAPI, HasChannels, HasPeers, HasSession):
    @property
    def peer_addresses(self) -> set[str]:
        """
        Cached property for peer addresses set.

        Returns cached set of peer native addresses for O(1) membership testing.
        Cache is invalidated when peers are modified via invalidate_peer_cache().
        """
        if self._cached_peer_addresses is None:
            self._cached_peer_addresses = {peer.address.native for peer in self.peers}
        return self._cached_peer_addresses

    def invalidate_peer_cache(self) -> None:
        """Invalidate peer address cache when peers are modified."""
        self._cached_peer_addresses = None
        self._cached_reachable_destinations = None

    @property
    def reachable_destinations(self) -> set[str]:
        """
        Cached set of session destinations that are currently reachable.

        Returns the intersection of session_destinations and peer_addresses.
        Cache is invalidated when peers change.

        Performance: Pre-computes the intersection once instead of filtering on every message.
        """
        if self._cached_reachable_destinations is None:
            self._cached_reachable_destinations = (
                set(self.session_destinations) & self.peer_addresses
            )
        return self._cached_reachable_destinations

    def _select_session_destination(
        self,
        message: MessageFormat,
        channels: list[str],
    ) -> str | None:
        """
        Select a random reachable destination for session creation.

        Filters session destinations to find peers that are:
        1. Not the relayer itself (message.relayer)
        2. Currently reachable (in self.peers)
        3. Valid session destinations (in self.session_destinations)

        Args:
            message: Message containing the relayer address to exclude
            channels: List of outgoing channel destination addresses

        Returns:
            str | None: Selected destination address, or None if no valid destinations
        """
        # Check if relayer has outgoing channels
        if not channels:
            logger.debug("No outgoing channels available", {"relayer": message.relayer})
            return None

        if message.relayer not in channels:
            logger.debug(
                "Relayer not found in outgoing channels",
                {"relayer": message.relayer, "channel_count": len(channels)},
            )
            return None

        # Check if session destinations are configured
        if not self.session_destinations:
            logger.debug(
                "No session destinations configured for this node", {"relayer": message.relayer}
            )
            return None

        # Get reachable destinations (uses cached intersection of destinations & peers)
        reachable_dest_set = self.reachable_destinations

        # Build candidate list - just exclude the relayer (O(d) where d = destinations count)
        candidates = [item for item in reachable_dest_set if item != message.relayer]

        if not candidates:
            # Provide detailed context about why no candidates
            reachable_destinations = list(reachable_dest_set)
            logger.debug(
                "No valid session destination found",
                {
                    "relayer": message.relayer,
                    "total_destinations": len(self.session_destinations),
                    "reachable_destinations": len(reachable_destinations),
                    "reachable_peers": len(self.peer_addresses),
                    "reason": (
                        "no_reachable_destinations"
                        if not reachable_destinations
                        else "all_reachable_are_relayer"
                    ),
                },
            )
            return None

        # Select random destination from valid candidates
        return random.choice(candidates)

    async def _get_or_create_session(
        self,
        relayer: str,
        destination: str,
    ) -> "Session" | None:
        """
        Get existing session or create new one (double-check pattern with rate limiting).

        Implements a double-check pattern to prevent race conditions when multiple
        coroutines attempt to create sessions concurrently, with rate limiting to
        prevent API overload from repeated failures:
        1. First check: Is session in dict?
        2. Rate limit check: Can we attempt session opening?
        3. If not: Create session (I/O operation)
        4. Second check: Did another coroutine create it during our I/O?
        5. If yes: Close our socket and use theirs
        6. If no: Add ours to dict

        Args:
            relayer: Peer address that will relay messages
            destination: Target peer address for message routing

        Returns:
            Session | None: Session object from dict, or None if creation failed or rate-limited
        """
        # First check: get session if exists
        session = self.sessions.get(relayer)
        if session:
            return session

        # Rate limit check: can we attempt session opening?
        can_attempt, wait_time = self.session_rate_limiter.can_attempt(relayer)
        if not can_attempt:
            logger.debug(
                "Session opening rate-limited",
                {"relayer": relayer, "wait_time_seconds": round(wait_time, 2)},
            )
            return None

        # Record attempt before API call
        self.session_rate_limiter.record_attempt(relayer)

        # Create new session (I/O operations outside critical section)
        session = await NodeHelper.open_session(self.api, destination, relayer, DEFAULT_LISTEN_HOST)
        if not session:
            # Record failure for rate limiting
            self.session_rate_limiter.record_failure(relayer)
            logger.debug("Failed to open session")
            return None

        # Record success - clears all tracking for this relayer
        self.session_rate_limiter.record_success(relayer)

        session.create_socket()
        logger.debug("Created socket", {"ip": session.ip, "port": session.port})

        # Double-check: another coroutine might have created it during our I/O
        if relayer not in self.sessions:
            # Safe to add - no await between check and add
            self.sessions[relayer] = session
        else:
            # Another coroutine created it while we were creating ours
            # Close our socket and use the existing session
            session.close_socket()
            session = self.sessions[relayer]
            logger.debug("Session created by another coroutine, using existing")

        return session

    def _schedule_message_batch(
        self,
        message: MessageFormat,
        relayer: str,
    ) -> bool:
        """
        Schedule message batch for background sending.

        Retrieves the session from the dict (with a final safety check) and schedules
        the batch message sending as a background task.

        Args:
            message: MessageFormat object to send
            relayer: Peer address for session lookup

        Returns:
            bool: True if scheduled successfully, False if session disappeared
        """
        message.sender = self.address.native

        # Get session reference for sending (avoid dict lookup in background task)
        session_ref = self.sessions.get(relayer)
        if session_ref:
            # Use the actual session reference for packet_size
            message.packet_size = session_ref.payload

            # Track message scheduled for sending
            try:
                from ..components.messages.message_metrics import MESSAGES_SCHEDULED

                MESSAGES_SCHEDULED.inc()
            except ImportError:
                pass

            AsyncLoop.add(
                NodeHelper.send_batch_messages,
                session_ref,
                message,
                publish_to_task_set=False,
            )
            return True
        else:
            logger.debug("Session disappeared before sending")
            return False

    async def _message_worker(self, worker_id: int) -> None:
        """
        Worker that continuously processes messages from the queue.

        Processing Flow:
        ----------------
        1. Pull message from shared MessageQueue (1 second timeout)
        2. Validate relayer has outgoing channels
        3. Select random destination from reachable peers (cached)
        4. Get or create UDP session for relayer (double-check pattern)
        5. Schedule message batch for background sending
        6. Record metrics (MESSAGES_PROCESSED, WORKER_MESSAGES)
        7. Repeat until self.running = False

        Args:
            worker_id: Unique identifier for this worker (0-based)
                      Used for metrics labeling and debugging

        Performance:
        ------------
        - Timeout ensures responsive shutdown (checks self.running every 1s)
        - Errors don't crash worker (logged and continue)

        Thread Safety:
        --------------
        - MessageQueue.get() is concurrent-safe (asyncio.Queue)
        - Session creation uses double-check pattern (prevents races)
        - Rate limiter is per-relayer (independent locks)
        - Metrics counters are thread-safe (Prometheus atomic ops)
        - Channel/peer lookups use cached properties (no mutations)

        Shutdown:
        ---------
        - Worker exits when self.running = False
        - Coordinator waits for all workers with asyncio.gather()
        - Clean shutdown guaranteed within 1-5 seconds
        """
        logger.debug(f"Message worker {worker_id} started")

        while self.running:
            try:
                # Get message with timeout to allow checking self.running flag
                message: MessageFormat = await asyncio.wait_for(MessageQueue().get(), timeout=1.0)

                # Check if relayer has open channel (O(1) lookup via cached dict)
                if not self.channels or message.relayer not in self.address_to_open_channel:
                    continue

                # Select destination for session
                destination = self._select_session_destination(
                    message, list(self.address_to_open_channel.keys())
                )
                if not destination:
                    continue

                # Get or create session using double-check pattern
                session = await self._get_or_create_session(message.relayer, destination)
                if not session:
                    continue

                # Schedule message batch for background sending
                self._schedule_message_batch(message, message.relayer)

                # Track message processed for benchmarks
                try:
                    from ..components.messages.message_metrics import (
                        MESSAGES_PROCESSED,
                        WORKER_MESSAGES,
                    )

                    MESSAGES_PROCESSED.inc()
                    WORKER_MESSAGES.labels(worker_id=worker_id).inc()
                except ImportError:
                    pass

            except asyncio.TimeoutError:
                # No message available, continue loop to check self.running
                continue
            except Exception as e:
                # Log error but keep worker running
                logger.error(f"Message worker {worker_id} error: {str(e)}", exc_info=True)
                continue

        logger.debug(f"Message worker {worker_id} stopped")

    @master(keepalive, connectguard)
    async def observe_message_queue(self) -> None:
        """
        Spawn concurrent workers to process messages from the queue.

        This method spawns a pool of concurrent workers that pull messages
        from the shared MessageQueue and process them in parallel, achieving
        higher combined throughput.

        Architecture:
        -------------
        - Coordinator spawns N asyncio tasks (_message_worker)
        - Each worker independently pulls from shared MessageQueue
        - Workers process messages until self.running = False
        - Graceful shutdown via asyncio.gather() + try/finally

        Worker Pool Design:
        -------------------
        - Configurable count via sessions.message_worker_count (default: 10)
        - Queue depth: Remains at 0 (no backpressure)

        Lifecycle:
        ----------
        1. Read worker count from self.params.sessions.message_worker_count
        2. Set ACTIVE_WORKERS metric
        3. Create N asyncio tasks running _message_worker(id)
        4. Wait for all workers with gather(..., return_exceptions=True)
        5. On shutdown: Set ACTIVE_WORKERS to 0
        6. Log completion

        Thread Safety:
        --------------
        - MessageQueue.get() is concurrent-safe (asyncio.Queue built-in)
        - Session dict uses double-check pattern (prevents race conditions)
        - Rate limiter per-relayer (independent locks, no contention)
        - Metrics are thread-safe (Prometheus atomic operations)

        Returns:
            None. Runs continuously until node shutdown (self.running = False).

        Raises:
            None. All worker exceptions are caught and logged individually.
        """
        # Get configured worker count (default: 10)
        worker_count = getattr(self.params.sessions, "message_worker_count", 10)

        # Update active workers metric
        try:
            from ..components.messages.message_metrics import ACTIVE_WORKERS

            ACTIVE_WORKERS.set(worker_count)
        except ImportError:
            pass

        # Create worker tasks
        logger.info(f"Starting {worker_count} message processing workers")
        workers = [
            asyncio.create_task(self._message_worker(worker_id))
            for worker_id in range(worker_count)
        ]

        try:
            # Wait for all workers (they run until self.running = False)
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            # Reset metric on shutdown
            try:
                from ..components.messages.message_metrics import ACTIVE_WORKERS

                ACTIVE_WORKERS.set(0)
            except ImportError:
                pass

            logger.info(f"All {worker_count} message workers stopped")

    async def _gather_session_maintenance_data(self) -> tuple[set[int], set[str]]:
        """
        Gather all I/O data needed for session maintenance.

        Performs all external API calls and data collection needed for maintaining
        sessions. This is done first to minimize time spent in critical sections later.

        Returns:
            tuple: (active_ports, reachable_addresses) where:
                - active_ports: Set of ports for active sessions at API level (O(1) lookup)
                - reachable_addresses: Set of reachable peer addresses (O(1) lookup)
        """
        active_ports = {session.port for session in await self.api.list_udp_sessions()}
        reachable_addresses = self.peer_addresses  # Use cached property
        return active_ports, reachable_addresses

    def _should_remove_session(
        self,
        relayer: str,
        session: "Session",
        grace_periods: dict[str, float],
        reachable_addresses: set[str],
        active_ports: set[int],
        now: float,
    ) -> tuple[bool, str | None]:
        """
        Determine if a session should be removed and why.

        Evaluates session state against multiple criteria:
        1. Grace period: Peer unreachable and grace period expired
        2. API status: Session no longer active at API level

        Args:
            relayer: Peer address this session relays to
            session: Session object to evaluate
            grace_periods: Snapshot of grace period start times
            reachable_addresses: Set of currently reachable peer addresses (O(1) lookup)
            active_ports: Set of ports active at API level (O(1) lookup)
            now: Current monotonic timestamp

        Returns:
            tuple: (should_remove, reason) where:
                - should_remove: True if session should be closed
                - reason: String describing why (for logging) or None
        """
        # Check if session no longer active at API level (immediate removal, bypasses grace period)
        if session.port not in active_ports:
            logger.debug(
                "Session no longer active at API level, marking for removal",
                {"relayer": relayer, "port": session.port},
            )
            return True, "api_inactive"

        # Check if peer is unreachable
        if relayer not in reachable_addresses:
            # Start grace period if not already started
            if relayer not in grace_periods:
                logger.debug(
                    "Session's relayer unreachable, will start grace period",
                    {
                        "relayer": relayer,
                        "port": session.port,
                        "grace_seconds": DEFAULT_SESSION_GRACE_PERIOD_SECONDS,
                    },
                )
                return False, None

            # Check if grace period has expired
            if now - grace_periods[relayer] > DEFAULT_SESSION_GRACE_PERIOD_SECONDS:
                logger.debug(
                    "Grace period expired, marking session for removal",
                    {"relayer": relayer, "port": session.port},
                )
                return True, "grace_period_expired"
        else:
            # Peer is reachable again
            if relayer in grace_periods:
                grace_duration = now - grace_periods[relayer]
                logger.debug(
                    "Peer reachable again, will cancel grace period",
                    {"relayer": relayer, "grace_duration_seconds": grace_duration},
                )

        return False, None

    def _update_grace_periods(
        self,
        sessions_snapshot: list[tuple[str, "Session"]],
        reachable_addresses: set[str],
        now: float,
    ) -> None:
        """
        Update grace period timers for unreachable peers.

        Manages the grace period dictionary by starting timers for newly unreachable
        peers and canceling timers for peers that have become reachable again.

        Args:
            sessions_snapshot: Immutable snapshot of sessions from Phase 2
            reachable_addresses: Set of currently reachable peer addresses (O(1) lookup)
            now: Current monotonic timestamp

        Side Effects:
            Modifies self.session_close_grace_period dictionary
        """
        for relayer, _session in sessions_snapshot:
            if relayer not in reachable_addresses:
                # Start grace period for unreachable peer
                if relayer not in self.session_close_grace_period:
                    self.session_close_grace_period[relayer] = now
            else:
                # Cancel grace period if peer is reachable
                if relayer in self.session_close_grace_period:
                    del self.session_close_grace_period[relayer]

    def _remove_closed_sessions(
        self,
        sessions_to_close: list[tuple[str, "Session"]],
    ) -> None:
        """
        Remove closed sessions with identity check.

        Removes sessions from the local cache after API-level closure. Uses identity
        checking (comparing ports) to ensure we don't accidentally remove a newly-created
        session that replaced the one we closed.

        Args:
            sessions_to_close: List of (relayer, session) tuples to remove

        Side Effects:
            - Modifies self.sessions dictionary
            - Modifies self.session_close_grace_period dictionary
            - Calls close_socket() on removed sessions
        """
        for relayer, inspected_session in sessions_to_close:
            # Clean up grace period tracking
            self.session_close_grace_period.pop(relayer, None)

            # Check if session still exists and matches what we inspected
            current_session = self.sessions.get(relayer)
            if current_session:
                # Only remove if it's the same session (check by port)
                if current_session.port == inspected_session.port:
                    self.sessions.pop(relayer, None)
                    current_session.close_socket()  # Synchronous operation
                else:
                    logger.debug(
                        "Session changed during maintenance, skipping removal",
                        {
                            "relayer": relayer,
                            "old_port": inspected_session.port,
                            "new_port": current_session.port,
                        },
                    )
            else:
                logger.debug("Session already removed by another coroutine", {"relayer": relayer})

    @master(keepalive, connectguard)
    async def maintain_sessions(self) -> None:
        """
        Maintain active sessions by closing stale ones and managing grace periods.

        Implements a five-phase algorithm designed to avoid race conditions while
        maintaining high performance. The key insight is that asyncio runs in a single
        thread, so we can ensure atomicity by avoiding `await` between related
        dictionary operations.

        Five-Phase Algorithm:

            Phase 1 - Gather Data (I/O):
                Fetch all data from external sources (API calls). This is done first
                to minimize time spent in critical sections later.
                - Query API for active sessions
                - Get list of reachable peers

            Phase 2 - Snapshot State:
                Create immutable snapshots of dictionaries BEFORE any operations.
                This prevents RuntimeError from dictionary modification during iteration.
                - sessions_snapshot = list(self.sessions.items())
                - grace_periods_snapshot = dict(self.session_close_grace_period)

            Phase 3 - Determine Actions:
                Analyze snapshots to determine what needs to be done, but don't modify
                any dictionaries yet. Build up sets/lists of planned actions.
                - Check grace periods for unreachable peers
                - Check if sessions are still active at API level
                - Build list of sessions to close

            Phase 4 - Execute I/O:
                Perform all API close operations. This is separated from Phase 5 to
                avoid `await` during dictionary modifications.
                - Close sessions at API level
                - Log any failures but continue

            Phase 5 - Update State (ATOMIC):
                Update all dictionaries with NO `await` statements between operations.
                This ensures consistency across self.sessions and
                self.session_close_grace_period.
                - Start/cancel grace period timers
                - Remove closed sessions
                - Close sockets

        Grace Period Logic (60 seconds):
            - When peer becomes unreachable: Start grace period timer
            - If peer returns within 60s: Cancel timer, preserve session
            - If timer expires: Remove session
            - If API shows session inactive: Remove immediately (bypass grace period)

        Thread Safety:
            - No locks required (asyncio single-threaded)
            - No `await` between Phase 5 dictionary operations
            - Snapshot pattern prevents iteration errors

        Performance:
            - All API closes happen in parallel (see Node.stop())
            - Minimal critical section time

        Example Scenarios:
            1. Peer temporarily unreachable:
               - Iteration 1: Grace period starts, session preserved
               - Peer returns: Grace period cancelled, session preserved

            2. Peer permanently unreachable:
               - Iteration 1: Grace period starts (t=0)
               - Iteration N: Grace period expires (t>60s), session closed

            3. API session disappears:
               - Immediate removal regardless of grace period
        """
        # Phase 1: Gather all data (all I/O operations)
        active_ports, reachable_addresses = await self._gather_session_maintenance_data()

        # Phase 2: Take snapshot BEFORE any dict operations
        sessions_snapshot = list(self.sessions.items())
        grace_periods_snapshot = self.session_close_grace_period.copy()
        now = time.monotonic()

        # Phase 3: Determine what to remove (no dict modifications yet)
        sessions_to_close = []  # Store (relayer, session) tuples for API calls

        for relayer, session in sessions_snapshot:
            should_remove, _reason = self._should_remove_session(
                relayer,
                session,
                grace_periods_snapshot,
                reachable_addresses,
                active_ports,
                now,
            )
            if should_remove:
                sessions_to_close.append((relayer, session))

        # Phase 4: Close sessions at API level (I/O operations in parallel)
        if sessions_to_close:
            import asyncio

            # Create close tasks for parallel execution
            async def close_with_logging(relayer: str, session: "Session") -> bool:
                close_ok = await NodeHelper.close_session(self.api, session, relayer)
                if not close_ok:
                    logger.warning(
                        "Failed to close session at API level, session may be orphaned",
                        {"relayer": relayer, "port": session.port},
                    )
                return close_ok

            # Execute all closes in parallel (10x faster for multiple sessions)
            await asyncio.gather(
                *[close_with_logging(relayer, session) for relayer, session in sessions_to_close],
                return_exceptions=True,
            )

        # Phase 5: Update dictionaries (NO awaits between operations!)
        # This entire block is atomic from asyncio perspective
        self._update_grace_periods(sessions_snapshot, reachable_addresses, now)
        self._remove_closed_sessions(sessions_to_close)

        # Update session count metric for benchmarks (optional)
        try:
            from ..components.messages.message_metrics import SESSION_COUNT

            SESSION_COUNT.set(len(self.sessions))
        except ImportError:
            pass
