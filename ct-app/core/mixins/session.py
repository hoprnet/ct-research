import logging
import random

from ..components.decorators import connectguard, keepalive, master
from ..components.logs import configure_logging
from ..components.messages import MessageFormat, MessageQueue
from ..components.socket_through_network import SocketThroughNetwork
from .protocols import HasAPI, HasChannels, HasParams, HasPeers, HasSession

configure_logging()
logger = logging.getLogger(__name__)


class SessionMixin(HasAPI, HasChannels, HasParams, HasPeers, HasSession):
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

        async with SocketThroughNetwork(self.api, destination, message.relayer) as socket:
            if not socket:
                return

            message.sender = self.address.native
            message.packet_size = socket.session.payload

            # taking into account the session opening packets
            batch_size: int = message.batch_size - 2

            [socket.send(message) for _ in range(batch_size)]
            await socket.receive(message.packet_size, batch_size * message.packet_size)
