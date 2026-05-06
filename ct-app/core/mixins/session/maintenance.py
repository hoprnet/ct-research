from __future__ import annotations

import asyncio
import logging
import time

from ...api.response_objects import Session
from ...messages.message_metrics import SESSION_COUNT
from ...components.decorators import connectguard, keepalive, master
from ...components.node_helper import NodeHelper
from .common import DEFAULT_SESSION_GRACE_PERIOD_SECONDS, SessionCommonMixin

logger = logging.getLogger(__name__)


class SessionMaintenanceMixin(SessionCommonMixin):
    async def _gather_session_maintenance_data(self) -> tuple[set[int] | None, set[str]]:
        active_sessions = await self.api.list_udp_sessions()
        active_ports = (
            {session.port for session in active_sessions} if active_sessions is not None else None
        )
        reachable_addresses = self.peer_addresses
        return active_ports, reachable_addresses

    def _should_remove_session(
        self,
        relayer: str,
        session: "Session",
        grace_periods: dict[str, float],
        reachable_addresses: set[str],
        active_ports: set[int] | None,
        now: float,
    ) -> tuple[bool, str | None]:
        if active_ports is not None and session.port not in active_ports:
            logger.debug(
                "Session no longer active at API level, marking for removal",
                {"relayer": relayer, "port": session.port},
            )
            return True, "api_inactive"

        if relayer not in reachable_addresses:
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

            if now - grace_periods[relayer] > DEFAULT_SESSION_GRACE_PERIOD_SECONDS:
                logger.debug(
                    "Grace period expired, marking session for removal",
                    {"relayer": relayer, "port": session.port},
                )
                return True, "grace_period_expired"
        elif relayer in grace_periods:
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
        for relayer, _session in sessions_snapshot:
            if relayer not in reachable_addresses:
                if relayer not in self.session_close_grace_period:
                    self.session_close_grace_period[relayer] = now
            elif relayer in self.session_close_grace_period:
                del self.session_close_grace_period[relayer]

    def _remove_closed_sessions(
        self,
        sessions_to_close: list[tuple[str, "Session"]],
    ) -> None:
        for relayer, inspected_session in sessions_to_close:
            self.session_close_grace_period.pop(relayer, None)

            current_session = self.sessions.get(relayer)
            if current_session:
                if current_session.port == inspected_session.port:
                    self.sessions.pop(relayer, None)
                    current_session.close_socket()
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
        active_ports, reachable_addresses = await self._gather_session_maintenance_data()

        sessions_snapshot = list(self.sessions.items())
        grace_periods_snapshot = self.session_close_grace_period.copy()
        now = time.monotonic()
        sessions_to_close: list[tuple[str, Session]] = []

        for relayer, session in sessions_snapshot:
            if self._session_has_in_flight_tasks(session):
                logger.debug(
                    "Skipping session cleanup while messages are in flight",
                    {"relayer": relayer, "port": session.port},
                )
                continue

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

        successfully_closed_sessions: list[tuple[str, "Session"]] = []
        if sessions_to_close:
            logger.info(
                "Closing sessions selected by maintenance pass",
                {"count": len(sessions_to_close)},
            )

            async def close_with_logging(
                relayer: str,
                session: "Session",
            ) -> tuple[str, "Session", bool]:
                close_ok = await NodeHelper.close_session(self.api, session, relayer)
                if not close_ok:
                    logger.warning(
                        "Failed to close session at API level, preserving local session state",
                        {"relayer": relayer, "port": session.port},
                    )
                return relayer, session, close_ok

            close_results = await asyncio.gather(
                *[close_with_logging(relayer, session) for relayer, session in sessions_to_close],
                return_exceptions=True,
            )

            for result in close_results:
                if isinstance(result, BaseException):
                    logger.exception(
                        "Session close raised unexpectedly, preserving local session state",
                        exc_info=result,
                    )
                    continue

                relayer, session, close_ok = result
                if close_ok:
                    successfully_closed_sessions.append((relayer, session))

        self._update_grace_periods(sessions_snapshot, reachable_addresses, now)
        self._remove_closed_sessions(successfully_closed_sessions)
        logger.debug(
            "Session maintenance pass complete",
            {
                "inspected": len(sessions_snapshot),
                "selected_for_close": len(sessions_to_close),
                "closed": len(successfully_closed_sessions),
                "active_sessions": len(self.sessions),
                "grace_period_entries": len(self.session_close_grace_period),
            },
        )
        SESSION_COUNT.set(len(self.sessions))
