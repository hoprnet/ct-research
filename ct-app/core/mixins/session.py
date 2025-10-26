from __future__ import annotations

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
        if not channels or message.relayer not in channels:
            return None

        try:
            # Get reachable peer addresses for filtering
            reachable_addresses = {peer.address.native for peer in self.peers}
            destination = random.choice(
                [
                    item
                    for item in self.session_destinations
                    if item != message.relayer and item in reachable_addresses
                ]
            )
            return destination
        except IndexError:
            logger.debug("No valid session destination found")
            return None

    async def _get_or_create_session(
        self,
        relayer: str,
        destination: str,
    ) -> "Session" | None:
        """
        Get existing session or create new one (double-check pattern).

        Implements the double-check pattern to prevent race conditions when multiple
        coroutines attempt to create sessions concurrently:
        1. First check: Is session in dict?
        2. If not: Create session (I/O operation)
        3. Second check: Did another coroutine create it during our I/O?
        4. If yes: Close our socket and use theirs
        5. If no: Add ours to dict

        Args:
            relayer: Peer address that will relay messages
            destination: Target peer address for message routing

        Returns:
            Session | None: Session object from dict, or None if creation failed
        """
        # First check: get session if exists
        session = self.sessions.get(relayer)
        if session:
            return session

        # Create new session (I/O operations outside critical section)
        session = await NodeHelper.open_session(self.api, destination, relayer, DEFAULT_LISTEN_HOST)
        if not session:
            logger.debug("Failed to open session")
            return None

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

    @master(keepalive, connectguard)
    async def observe_message_queue(self):
        """
        Monitor the message queue and create/reuse sessions for message relay.

        This method continuously monitors the message queue and ensures that sessions
        exist for relaying messages. It implements the double-check pattern to prevent
        race conditions when multiple coroutines attempt to create sessions concurrently.

        Double-Check Pattern:
            1. Check if session exists (first check)
            2. If not, perform I/O to create session
            3. Check again before adding to dict (second check)
            4. If another coroutine created it meanwhile, close our socket and use theirs

        This pattern ensures only one session exists per relayer without using locks.

        Thread Safety:
            - Uses dict.get() which is atomic in Python
            - No await between final dict check and dict assignment
            - Closes duplicate sockets if race condition occurs

        Flow:
            1. Get message from queue
            2. Validate relayer has outgoing channel
            3. Select random reachable destination
            4. Get or create session using double-check pattern
            5. Launch background task to send messages

        Returns:
            None. Operates continuously as a keepalive task.
        """
        # Get message and validate channels
        channels: list[str] = (
            [channel.destination for channel in self.channels.outgoing] if self.channels else []
        )
        message: MessageFormat = await MessageQueue().get()

        # Select destination for session
        destination = self._select_session_destination(message, channels)
        if not destination:
            return

        # Get or create session using double-check pattern
        session = await self._get_or_create_session(message.relayer, destination)
        if not session:
            return

        # Schedule message batch for background sending
        self._schedule_message_batch(message, message.relayer)

    async def _gather_session_maintenance_data(self) -> tuple[list[int], list[str]]:
        """
        Phase 1: Gather all I/O data needed for session maintenance.

        Performs all external API calls and data collection needed for maintaining
        sessions. This is done first to minimize time spent in critical sections later.

        Returns:
            tuple: (active_ports, reachable_addresses) where:
                - active_ports: List of ports for currently active sessions at API level
                - reachable_addresses: List of native addresses for reachable peers
        """
        active_ports = [session.port for session in await self.api.list_udp_sessions()]
        reachable_addresses = [peer.address.native for peer in self.peers]
        return active_ports, reachable_addresses

    def _should_remove_session(
        self,
        relayer: str,
        session: "Session",
        grace_periods: dict[str, float],
        reachable_addresses: list[str],
        active_ports: list[int],
        now: float,
    ) -> tuple[bool, str | None]:
        """
        Phase 3: Determine if a session should be removed and why.

        Evaluates session state against multiple criteria:
        1. Grace period: Peer unreachable and grace period expired
        2. API status: Session no longer active at API level

        Args:
            relayer: Peer address this session relays to
            session: Session object to evaluate
            grace_periods: Snapshot of grace period start times
            reachable_addresses: List of currently reachable peer addresses
            active_ports: List of ports active at API level
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
        reachable_addresses: list[str],
        now: float,
    ) -> None:
        """
        Phase 5a: Update grace period timers for unreachable peers.

        Manages the grace period dictionary by starting timers for newly unreachable
        peers and canceling timers for peers that have become reachable again.

        Args:
            sessions_snapshot: Immutable snapshot of sessions from Phase 2
            reachable_addresses: List of currently reachable peer addresses
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
        Phase 5b: Remove closed sessions with identity check.

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
    async def maintain_sessions(self):
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
            - O(n) where n = number of sessions
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
        grace_periods_snapshot = dict(self.session_close_grace_period)
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

        # Phase 4: Close sessions at API level (I/O operations)
        for relayer, session in sessions_to_close:
            close_ok = await NodeHelper.close_session(self.api, session, relayer)
            if not close_ok:
                logger.warning(
                    "Failed to close session at API level, session may be orphaned",
                    {"relayer": relayer, "port": session.port},
                )
                # Still proceed with local cleanup, but log the issue

        # Phase 5: Update dictionaries (NO awaits between operations!)
        # This entire block is atomic from asyncio perspective
        self._update_grace_periods(sessions_snapshot, reachable_addresses, now)
        self._remove_closed_sessions(sessions_to_close)
