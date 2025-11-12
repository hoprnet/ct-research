"""
Session rate limiter to prevent API overload from failed session attempts.

Implements exponential backoff for failed session opening attempts to prevent
cascading failures and API overload.
"""

import logging
import time
from typing import Optional

from .logs import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


class SessionRateLimiter:
    """
    Rate limiter for session opening attempts with exponential backoff.

    Tracks failed session attempts per relayer and enforces delays before
    allowing retry attempts. Uses exponential backoff to progressively
    increase delays for repeated failures.

    Algorithm:
        - First failure: base_delay seconds
        - Second failure: base_delay * 2 seconds
        - Third failure: base_delay * 4 seconds
        - ...capped at max_delay seconds

    Thread Safety:
        Safe for asyncio single-threaded environment. All operations are
        synchronous and use dict operations which are atomic in Python.
    """

    def __init__(
        self,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
    ):
        """
        Initialize the rate limiter.

        Args:
            base_delay: Base delay in seconds after first failure (default: 2.0)
            max_delay: Maximum delay in seconds (default: 60.0)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay

        # Track failure count per relayer
        self._failure_count: dict[str, int] = {}

        # Track last attempt timestamp per relayer
        self._last_attempt: dict[str, float] = {}

    def can_attempt(self, relayer: str) -> tuple[bool, Optional[float]]:
        """
        Check if a session opening attempt is allowed for the relayer.

        Args:
            relayer: Peer address to check

        Returns:
            tuple: (can_attempt, wait_time) where:
                - can_attempt: True if attempt is allowed, False if rate-limited
                - wait_time: Remaining seconds to wait if rate-limited, None if allowed
        """
        # Check if enough time has passed since last attempt
        last_attempt = self._last_attempt.get(relayer)
        if last_attempt is None:
            # No previous attempt, allow immediately
            return True, None

        now = time.monotonic()
        elapsed = now - last_attempt

        # Calculate required delay based on failure count (exponential backoff)
        failure_count = self._failure_count.get(relayer, 0)
        required_delay = min(self.base_delay * (2**failure_count), self.max_delay)

        if elapsed >= required_delay:
            # Enough time has passed
            return True, None
        else:
            # Still rate-limited
            wait_time = required_delay - elapsed
            return False, wait_time

    def record_attempt(self, relayer: str) -> None:
        """
        Record a session opening attempt.

        Should be called immediately before making the API call.

        Args:
            relayer: Peer address being attempted
        """
        self._last_attempt[relayer] = time.monotonic()

    def record_failure(self, relayer: str) -> None:
        """
        Record a failed session opening attempt.

        Increments failure count for exponential backoff calculation.

        Args:
            relayer: Peer address that failed
        """
        self._failure_count[relayer] = self._failure_count.get(relayer, 0) + 1
        failure_count = self._failure_count[relayer]

        # Calculate next backoff delay
        next_delay = min(self.base_delay * (2**failure_count), self.max_delay)

        logger.debug(
            "Session opening failed, applying backoff",
            {
                "relayer": relayer,
                "failures": failure_count,
                "next_delay_seconds": next_delay,
            },
        )

    def record_success(self, relayer: str) -> None:
        """
        Record a successful session opening.

        Clears all tracking for the relayer, allowing immediate future attempts.

        Args:
            relayer: Peer address that succeeded
        """
        if relayer in self._failure_count:
            failure_count = self._failure_count[relayer]
            logger.debug(
                "Session opened successfully, clearing backoff",
                {"relayer": relayer, "previous_failures": failure_count},
            )
            del self._failure_count[relayer]

        if relayer in self._last_attempt:
            del self._last_attempt[relayer]

    def reset(self, relayer: Optional[str] = None) -> None:
        """
        Reset tracking for a specific relayer or all relayers.

        Args:
            relayer: Specific peer address to reset, or None to reset all
        """
        if relayer:
            self._failure_count.pop(relayer, None)
            self._last_attempt.pop(relayer, None)
        else:
            self._failure_count.clear()
            self._last_attempt.clear()

    def get_stats(self, relayer: str) -> dict:
        """
        Get current rate limiting stats for a relayer.

        Args:
            relayer: Peer address to query

        Returns:
            dict with keys: failures, last_attempt_age_seconds, can_attempt, wait_time
        """
        failure_count = self._failure_count.get(relayer, 0)
        last_attempt = self._last_attempt.get(relayer)

        can_attempt, wait_time = self.can_attempt(relayer)

        return {
            "failures": failure_count,
            "last_attempt_age_seconds": (time.monotonic() - last_attempt if last_attempt else None),
            "can_attempt": can_attempt,
            "wait_time_seconds": wait_time,
        }
