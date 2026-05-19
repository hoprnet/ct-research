import time

from ..components.decorators import keepalive
from ..config_parser.parameters import Parameters
from ..types.message_queue import MessageQueue
from ..types.peer import Peer
from .runtime_state import NodeRuntimeState


class PeerRelayMixin(NodeRuntimeState):
    peers: dict[str, Peer]
    params: Parameters

    async def _relay_messages_once(self):
        if not self.peers:
            return

        queue = MessageQueue()
        min_delay = self.params.peer.minimum_delay_between_batches.value
        now = time.monotonic()

        current_relayers = set(self.peers.keys())
        for stale_relayer in list(self._next_relay_at.keys()):
            if stale_relayer not in current_relayers:
                self._next_relay_at.pop(stale_relayer, None)

        for peer in self.peers.values():
            if peer.yearly_message_count is None:
                self._next_relay_at.pop(peer.address.native, None)
                continue

            delay = peer.message_delay
            if delay is None:
                continue

            message = peer.build_relay_request(delay, min_delay)
            send_interval = delay * message.batch_size
            next_send_at = self._next_relay_at.get(peer.address.native, now)
            if now < next_send_at:
                continue

            await queue.put(message)
            self._next_relay_at[peer.address.native] = now + send_interval

    @keepalive
    async def relay_messages(self):
        await self._relay_messages_once()
