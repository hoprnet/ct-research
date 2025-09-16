import logging
import random

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

        AsyncLoop.add(
            NodeHelper.send_batch_messages,
            self.api,
            self.address.native,
            destination,
            message,
            publish_to_task_set=False,
        )
