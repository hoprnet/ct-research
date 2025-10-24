"""
SessionMixin - Session lifecycle management for HOPR nodes.

This mixin provides session management functionality including:
- Automatic session creation when messages need to be sent
- Grace period mechanism to prevent premature session closure
- Lock-free thread-safe session operations
- Parallel session cleanup on shutdown

Key Concepts:

    Grace Period (60 seconds):
        When a peer becomes unreachable, sessions are not immediately closed.
        Instead, a 60-second grace period begins. If the peer becomes reachable
        again within this window, the session is preserved. This prevents session
        churn during temporary network issues.

    Lock-Free Thread Safety:
        Instead of using asyncio.Lock, this implementation leverages the fact that
        asyncio runs in a single thread. By avoiding `await` statements between
        related dictionary operations, we ensure atomicity without locks.

    Double-Check Pattern:
        When creating sessions, we check if a session exists, perform I/O to create
        it, then check again before adding to the dict. This prevents race conditions
        where multiple coroutines might create sessions for the same relayer.

    Five-Phase Maintenance Algorithm:
        maintain_sessions() uses a carefully designed 5-phase approach to avoid
        race conditions while maintaining performance. See maintain_sessions()
        docstring for details.

Thread Safety Guarantees:
    - No RuntimeError from dictionary modification during iteration
    - No duplicate sessions for the same relayer
    - No use-after-free of session objects
    - Consistent state across concurrent operations
"""

import logging
import random
import time

from ..components.asyncloop import AsyncLoop
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.messages import MessageFormat, MessageQueue
from ..components.node_helper import NodeHelper
from .protocols import HasAPI, HasChannels, HasPeers, HasSession

configure_logging()
logger = logging.getLogger(__name__)


class SessionMixin(HasAPI, HasChannels, HasPeers, HasSession):
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
        channels: list[str] = (
            [channel.destination for channel in self.channels.outgoing] if self.channels else []
        )

        message: MessageFormat = await MessageQueue().get()

        if not channels or message.relayer not in channels:
            return

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
        except IndexError:
            logger.debug("No valid session destination found")
            return

        # First check: get session if exists
        session = self.sessions.get(message.relayer)

        # If no session, create one
        if not session:
            # I/O operations (outside critical section)
            session = await NodeHelper.open_session(
                self.api, destination, message.relayer, "127.0.0.1"
            )
            if not session:
                logger.debug("Failed to open session")
                return

            session.create_socket()
            logger.debug("Created socket", {"ip": session.ip, "port": session.port})

            # Double-check: another coroutine might have created it during our I/O
            if message.relayer not in self.sessions:
                # Safe to add - no await between check and add
                self.sessions[message.relayer] = session
            else:
                # Another coroutine created it while we were creating ours
                # Close our socket and use the existing session
                session.close_socket()
                session = self.sessions[message.relayer]
                logger.debug("Session created by another coroutine, using existing")

        # At this point, session is guaranteed to be in dict
        # Get a local reference (no await between get and use)
        message.sender = self.address.native

        # Get session reference for sending (avoid dict lookup in background task)
        session_ref = self.sessions.get(message.relayer)
        if session_ref:
            # Use the actual session reference for packet_size
            message.packet_size = session_ref.payload
            AsyncLoop.add(
                NodeHelper.send_batch_messages,
                session_ref,
                message,
                publish_to_task_set=False,
            )
        else:
            logger.debug("Session disappeared before sending")

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
        active_sessions_ports: list[int] = [
            session.port for session in await self.api.list_udp_sessions()
        ]
        reachable_peers_addresses = [peer.address.native for peer in self.peers]

        # Phase 2: Take snapshot BEFORE any dict operations
        sessions_snapshot = list(self.sessions.items())
        grace_periods_snapshot = dict(self.session_close_grace_period)

        GRACE_PERIOD_SECONDS = 60  # 1 minute grace period
        now = time.monotonic()

        # Phase 3: Determine what to remove (no dict modifications yet)
        session_relayers_to_remove = set[str]()
        sessions_to_close = []  # Store (relayer, session) tuples for API calls

        for relayer, session in sessions_snapshot:
            should_remove = False

            # Check if peer is unreachable
            if relayer not in reachable_peers_addresses:
                # Start grace period if not already started
                if relayer not in grace_periods_snapshot:
                    # Will start timer in Phase 5
                    logger.debug(
                        "Session's relayer unreachable, will start grace period",
                        {
                            "relayer": relayer,
                            "port": session.port,
                            "grace_seconds": GRACE_PERIOD_SECONDS,
                        },
                    )
                # Check if grace period has expired
                elif now - grace_periods_snapshot[relayer] > GRACE_PERIOD_SECONDS:
                    should_remove = True
                    logger.debug(
                        "Grace period expired, marking session for removal",
                        {"relayer": relayer, "port": session.port},
                    )
            else:
                # Peer is reachable again
                if relayer in grace_periods_snapshot:
                    grace_duration = now - grace_periods_snapshot[relayer]
                    logger.debug(
                        "Peer reachable again, will cancel grace period",
                        {"relayer": relayer, "grace_duration_seconds": grace_duration},
                    )

            # Check if session no longer active at API level (immediate removal)
            if session.port not in active_sessions_ports:
                should_remove = True
                logger.debug(
                    "Session no longer active at API level, marking for removal",
                    {"relayer": relayer, "port": session.port},
                )

            if should_remove:
                session_relayers_to_remove.add(relayer)
                sessions_to_close.append((relayer, session))

        # Phase 4: Close sessions at API level (I/O operations)
        sessions_failed_to_close = []

        for relayer, session in sessions_to_close:
            close_ok = await NodeHelper.close_session(self.api, session, relayer)

            if not close_ok:
                logger.warning(
                    "Failed to close session at API level, session may be orphaned",
                    {"relayer": relayer, "port": session.port},
                )
                sessions_failed_to_close.append(relayer)
                # Still proceed with local cleanup, but log the issue

        # Phase 5: Update dictionaries (NO awaits between operations!)
        # This entire block is atomic from asyncio perspective

        # Update grace periods for unreachable peers
        for relayer, session in sessions_snapshot:
            if relayer not in reachable_peers_addresses:
                if relayer not in self.session_close_grace_period:
                    self.session_close_grace_period[relayer] = now
            else:
                # Cancel grace period if peer is reachable
                if relayer in self.session_close_grace_period:
                    del self.session_close_grace_period[relayer]

        # Remove closed sessions (still no awaits!)
        # Use sessions_to_close to get the inspected session for identity check
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
