import logging
import random
from datetime import datetime

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
        channels: list[str] = (
            [channel.destination for channel in self.channels.outgoing] if self.channels else []
        )

        message: MessageFormat = await MessageQueue().get()

        if not channels or message.relayer not in channels:
            return

        try:
            destination = random.choice(
                [
                    item
                    for item in self.session_destinations
                    if item != message.relayer and item in self.peers
                ]
            )
        except IndexError:
            logger.debug("No valid session destination found")
            return

        if session := self.sessions.get(message.relayer):
            pass
        else:
            session = await NodeHelper.open_session(
                self.api, destination, message.relayer, "127.0.0.1"
            )
            if not session:
                logger.debug("Failed to open session")
                return

            session.create_socket()
            logger.debug("Created socket", {"ip": session.ip, "port": session.port})
            self.sessions[message.relayer] = session

        message.sender = self.address.native
        message.packet_size = session.payload

        AsyncLoop.add(
            NodeHelper.send_batch_messages,
            self.sessions[message.relayer],
            message,
            publish_to_task_set=False,
        )

    @master(keepalive, connectguard)
    async def maintain_sessions(self):
        active_sessions_ports: list[str] = [
            session.port for session in await self.api.list_udp_sessions()
        ]
        reachable_peers_addresses = [peer.address.native for peer in self.peers]
        session_relayers_to_remove = set[str]()

        GRACE_PERIOD_SECONDS = 60  # 1 minute grace period
        now = datetime.now().timestamp()

        for relayer, session in self.sessions.items():
            should_remove = False

            # Check if peer is unreachable
            if relayer not in reachable_peers_addresses:
                # Start grace period if not already started
                if relayer not in self.session_close_grace_period:
                    self.session_close_grace_period[relayer] = now
                    logger.debug(
                        "Session's relayer unreachable, starting grace period",
                        {"relayer": relayer, "port": session.port, "grace_seconds": GRACE_PERIOD_SECONDS},
                    )
                # Check if grace period has expired
                elif now - self.session_close_grace_period[relayer] > GRACE_PERIOD_SECONDS:
                    should_remove = True
                    logger.debug(
                        "Grace period expired, marking session for removal",
                        {"relayer": relayer, "port": session.port},
                    )
            else:
                # Peer is reachable again, cancel grace period
                if relayer in self.session_close_grace_period:
                    grace_duration = now - self.session_close_grace_period[relayer]
                    del self.session_close_grace_period[relayer]
                    logger.debug(
                        "Peer reachable again, canceling grace period",
                        {"relayer": relayer, "grace_duration_seconds": grace_duration},
                    )

            # Check if session no longer active at API level (immediate removal)
            if session.port not in active_sessions_ports:
                should_remove = True
                logger.debug(
                    "Session no longer active at API level, marking for removal",
                    {"relayer": relayer, "port": session.port},
                )

            # Mark for removal if needed
            if should_remove:
                await NodeHelper.close_session(self.api, session, relayer)
                session_relayers_to_remove.add(relayer)

        for relayer in session_relayers_to_remove:
            # Clean up grace period tracking
            self.session_close_grace_period.pop(relayer, None)

            if session := self.sessions.pop(relayer, None):
                session.close_socket()
            else:
                logger.warning("Session to remove not found in cache", {"relayer": relayer})
