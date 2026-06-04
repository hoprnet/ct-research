import asyncio
import time

from ..components.decorators import keepalive
from ..config_parser.parameters import Parameters
from ..types.message_queue import MessageQueue
from ..types.peer import Peer
from ..services.relay_pacer import RelayPacer
from .runtime_state import NodeRuntimeState

IDLE_NO_WORK_SLEEP_SECONDS = 1.0


class PeerRelayMixin(NodeRuntimeState):
    peers: dict[str, Peer]
    params: Parameters
    relay_pacer: RelayPacer

    async def _relay_messages_once(self) -> float | None:
        if not self.peers:
            return IDLE_NO_WORK_SLEEP_SECONDS

        queue = MessageQueue()
        min_delay = self.params.peer.minimum_delay_between_batches.value
        due_messages, next_due_in_seconds = self.relay_pacer.due_messages(
            self.peers,
            min_delay,
            time.monotonic(),
        )
        for message in due_messages:
            await queue.put(message)

        if due_messages:
            return None

        return next_due_in_seconds or IDLE_NO_WORK_SLEEP_SECONDS

    @keepalive
    async def relay_messages(self):
        sleep_seconds = await self._relay_messages_once()
        if sleep_seconds is not None:
            await asyncio.sleep(sleep_seconds)
