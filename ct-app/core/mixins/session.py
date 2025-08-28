import asyncio
import logging
import random

from ..api import Protocol
from ..api.response_objects import Session
from ..components.asyncloop import AsyncLoop
from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.messages import MessageFormat, MessageQueue
from ..components.node_helper import ManageSession, NodeHelper
from ..components.session_to_socket import SessionToSocket
from .protocols import HasAPI, HasChannels, HasParams, HasSession

configure_logging()
logger = logging.getLogger(__name__)


class SessionMixin(HasAPI, HasChannels, HasParams, HasSession):
    async def close_all_sessions(self):
        """
        Close all sessions without checking if they are active, or if a socket is associated.
        This method should run on startup to clean up any old sessions.
        """
        active_sessions: list[Session] = await self.api.list_sessions(Protocol.UDP)

        for session in active_sessions:
            AsyncLoop.add(
                NodeHelper.close_session,
                self.api,
                session,
                publish_to_task_set=False,
            )

    @master(keepalive, connectguard)
    async def observe_message_queue(self):
        channels: list[str] = (
            [channel.destination for channel in self.channels.outgoing] if self.channels else []
        )

        if not channels:
            await asyncio.sleep(2)
            return

        message: MessageFormat = await MessageQueue().get_async()

        if message.relayer not in channels:
            return

        destination = random.choice(
            [item for item in self.session_destinations if item not in [message.relayer]]
        )

        async with ManageSession(self.api, destination, message.relayer) as session:
            if not session:
                return

            sess_and_socket = SessionToSocket(session)

            message.sender = self.address.native
            message.packet_size = sess_and_socket.session.payload

            [sess_and_socket.send(message) for _ in range(self.params.sessions.batch_size)]
            await sess_and_socket.receive(
                message.packet_size, self.params.sessions.batch_size * message.packet_size
            )

            sess_and_socket.close_socket()
