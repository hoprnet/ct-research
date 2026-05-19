import time

from ..components.decorators import keepalive
from ..config_parser.parameters import Parameters
from ..types.message_queue import MessageQueue
from ..types.peer import Peer
from ..services.relay_pacer import RelayPacer
from .runtime_state import NodeRuntimeState


class PeerRelayMixin(NodeRuntimeState):
    peers: dict[str, Peer]
    params: Parameters
    relay_pacer: RelayPacer

    async def _relay_messages_once(self):
        if not self.peers:
            return

        queue = MessageQueue()
        min_delay = self.params.peer.minimum_delay_between_batches.value
        due_messages = self.relay_pacer.due_messages(self.peers, min_delay, time.monotonic())
        for message in due_messages:
            await queue.put(message)

    @keepalive
    async def relay_messages(self):
        await self._relay_messages_once()
