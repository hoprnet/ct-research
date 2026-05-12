from __future__ import annotations

import asyncio
import logging

from ...api.response_objects import Session
from ...types.asyncloop import AsyncLoop
from ...components.decorators import connectguard, keepalive, master
from ...types.message_format import MessageFormat
from ...types.message_queue import MessageQueue
from ...messages.message_metrics import (
    ACTIVE_WORKERS,
    BATCH_SCHEDULE_FAILURES,
    MESSAGE_REQUEUES,
    MESSAGES_PROCESSED,
    MESSAGES_SCHEDULED,
    SESSION_OPEN_EVENTS,
    WORKER_LOOP_EVENTS,
    WORKER_MESSAGES,
)
from ...components.node_helper import NodeHelper
from .common import (
    DEFAULT_IN_FLIGHT_WAIT_SECONDS,
    DEFAULT_LISTEN_HOST,
    SessionCommonMixin,
)

logger = logging.getLogger(__name__)


class SessionWorkerMixin(SessionCommonMixin):
    def _track_in_flight_message_task(self, session: "Session", task: asyncio.Task) -> None:
        self._in_flight_message_tasks.add(task)
        port_tasks = self._in_flight_tasks_by_session_port.setdefault(session.port, set())
        port_tasks.add(task)

        def _discard(completed_task: asyncio.Task) -> None:
            self._in_flight_message_tasks.discard(completed_task)
            tracked_tasks = self._in_flight_tasks_by_session_port.get(session.port)
            if tracked_tasks is None:
                return
            tracked_tasks.discard(completed_task)
            if not tracked_tasks:
                self._in_flight_tasks_by_session_port.pop(session.port, None)

        task.add_done_callback(_discard)

    def _session_has_in_flight_tasks(self, session: "Session") -> bool:
        return bool(self._in_flight_tasks_by_session_port.get(session.port))

    async def _wait_for_session_tasks(
        self,
        session: "Session",
        timeout: float = DEFAULT_IN_FLIGHT_WAIT_SECONDS,
    ) -> None:
        tasks = list(self._in_flight_tasks_by_session_port.get(session.port, set()))
        if not tasks:
            return

        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for in-flight session tasks",
                {"port": session.port, "task_count": len(tasks), "timeout_seconds": timeout},
            )

    async def wait_for_in_flight_messages(
        self,
        timeout: float = DEFAULT_IN_FLIGHT_WAIT_SECONDS,
    ) -> None:
        tasks = list(self._in_flight_message_tasks)
        if not tasks:
            return

        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Timed out waiting for in-flight message tasks",
                {"task_count": len(tasks), "timeout_seconds": timeout},
            )

    async def _retire_session(
        self,
        relayer: str,
        session: "Session",
        reason: str,
        wait_for_in_flight: bool = True,
    ) -> bool:
        if wait_for_in_flight:
            await self._wait_for_session_tasks(session)

        self.session_lifecycle_coordinator.mark("retire_requested")
        close_ok = await NodeHelper.close_session(self.api, session, relayer)
        if not close_ok:
            self.session_lifecycle_coordinator.mark("retire_failed")
            logger.warning(
                "Failed to close session while retiring local cache entry",
                {"relayer": relayer, "port": session.port, "reason": reason},
            )
            return False

        current_session = self.sessions.get(relayer)
        if current_session and current_session.port == session.port:
            self.sessions.pop(relayer, None)

        session.close_socket()
        self.session_close_grace_period.pop(relayer, None)
        self.session_lifecycle_coordinator.mark("retired")
        return True

    async def _get_or_create_session(
        self,
        relayer: str,
        destination: str,
    ) -> "Session" | None:
        session = self.sessions.get(relayer)
        if session:
            if self._session_matches_destination(session, destination):
                SESSION_OPEN_EVENTS.labels(result="reused_existing").inc()
                return session

            logger.info(
                "Replacing cached session with different destination",
                {
                    "relayer": relayer,
                    "cached_target": session.target,
                    "requested_destination": destination,
                    "port": session.port,
                },
            )
            retired = await self._retire_session(
                relayer,
                session,
                reason="destination_mismatch",
            )
            if not retired:
                logger.warning(
                    "Preserving current session because replacement retirement failed",
                    {
                        "relayer": relayer,
                        "cached_target": session.target,
                        "requested_destination": destination,
                        "port": session.port,
                    },
                )
                return None

        pending_session = self._pending_session_creations.get(relayer)
        if pending_session is not None:
            return await pending_session

        async def open_session() -> "Session" | None:
            self.session_lifecycle_coordinator.mark("open_requested")
            can_attempt, wait_time = self.session_rate_limiter.can_attempt(relayer)
            if not can_attempt and wait_time:
                logger.debug(
                    "Session opening rate-limited",
                    {"relayer": relayer, "wait_time_seconds": round(wait_time, 2)},
                )
                SESSION_OPEN_EVENTS.labels(result="rate_limited").inc()
                self.session_lifecycle_coordinator.mark("open_rate_limited")
                return None

            self.session_rate_limiter.record_attempt(relayer)

            session = await NodeHelper.open_session(
                self.api,
                destination,
                relayer,
                DEFAULT_LISTEN_HOST,
            )
            if not session:
                self.session_rate_limiter.record_failure(relayer)
                logger.debug("Failed to open session")
                SESSION_OPEN_EVENTS.labels(result="failed").inc()
                self.session_lifecycle_coordinator.mark("open_failed")
                return None

            self.session_rate_limiter.record_success(relayer)
            SESSION_OPEN_EVENTS.labels(result="opened").inc()
            self.session_lifecycle_coordinator.mark("opened")

            session.create_socket()
            logger.debug("Created socket", {"ip": session.ip, "port": session.port})

            if relayer not in self.sessions:
                self.sessions[relayer] = session
                return session

            session.close_socket()
            logger.debug("Session created by another coroutine, using existing")
            self.session_lifecycle_coordinator.mark("open_race_reused")
            return self.sessions[relayer]

        task = asyncio.create_task(open_session())
        self._pending_session_creations[relayer] = task
        try:
            return await task
        finally:
            if self._pending_session_creations.get(relayer) is task:
                self._pending_session_creations.pop(relayer, None)

    def _schedule_message_batch(
        self,
        message: MessageFormat,
        relayer: str,
    ) -> bool:
        message.sender = self.address.native
        session_ref = self.sessions.get(relayer)
        if session_ref:
            message.packet_size = session_ref.payload
            MESSAGES_SCHEDULED.inc()

            task = AsyncLoop.add(
                NodeHelper.send_batch_messages,
                session_ref,
                message,
                publish_to_task_set=False,
            )
            if task is None:
                logger.debug("Failed to schedule message batch", {"relayer": relayer})
                BATCH_SCHEDULE_FAILURES.inc()
                return False
            self._track_in_flight_message_task(session_ref, task)
            return True

        logger.debug("Session disappeared before sending")
        return False

    async def _requeue_message(self, message: MessageFormat, reason: str) -> bool:
        MESSAGE_REQUEUES.labels(reason=reason).inc()
        logger.debug("Requeueing message for retry", {"relayer": message.relayer, "reason": reason})
        await MessageQueue().put(message)
        return False

    async def _process_message(self, message: MessageFormat, worker_id: int) -> bool:
        if not self.channels or message.relayer not in self.address_to_open_channel:
            return await self._requeue_message(message, "no_open_channel")

        destination = self._select_session_destination(
            message, list(self.address_to_open_channel.keys())
        )
        if not destination:
            return await self._requeue_message(message, "no_destination")

        session = await self._get_or_create_session(message.relayer, destination)
        if not session:
            return await self._requeue_message(message, "session_unavailable")

        if not self._schedule_message_batch(message, message.relayer):
            return await self._requeue_message(message, "session_disappeared")

        MESSAGES_PROCESSED.inc()
        WORKER_MESSAGES.labels(worker_id=worker_id).inc()

        return True

    async def _message_worker(self, worker_id: int) -> None:
        logger.debug("Message worker started", {"worker_id": worker_id})

        while self.running:
            try:
                message: MessageFormat = await asyncio.wait_for(MessageQueue().get(), timeout=1.0)
                await self._process_message(message, worker_id)
            except asyncio.CancelledError:
                logger.debug("Message worker cancelled", {"worker_id": worker_id})
                raise
            except asyncio.TimeoutError:
                WORKER_LOOP_EVENTS.labels(event="timeout").inc()
                logger.debug("Message worker %s timed out waiting for work", worker_id)
                continue
            except Exception as err:
                logger.error(
                    "Message worker failed while processing queue item",
                    {
                        "worker_id": worker_id,
                        "error": str(err),
                    },
                    exc_info=True,
                )
                continue

        logger.debug("Message worker stopped", {"worker_id": worker_id})

    @master(keepalive, connectguard)
    async def observe_message_queue(self) -> None:
        worker_count = getattr(self.params.sessions, "message_worker_count", 10)
        ACTIVE_WORKERS.set(worker_count)

        logger.info("Starting message processing workers", {"worker_count": worker_count})
        workers = [
            asyncio.create_task(self._message_worker(worker_id))
            for worker_id in range(worker_count)
        ]

        try:
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            ACTIVE_WORKERS.set(0)
            logger.info("All message workers stopped", {"worker_count": worker_count})
