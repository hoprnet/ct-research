import asyncio

from ..components.decorators import keepalive
from ..config_parser.parameters import Parameters
from ..types.message_queue import MessageQueue
from ..types.peer import Peer
from .runtime_state import NodeRuntimeState


class PeerRelayMixin(NodeRuntimeState):
    peers: dict[str, Peer]
    params: Parameters

    @keepalive
    async def relay_messages(self):
        if not self.peers:
            return

        queue = MessageQueue()
        min_delay = self.params.peer.minimum_delay_between_batches.value
        sleep_mean = self.params.peer.sleep_mean_time.value
        sleep_std = self.params.peer.sleep_std_time.value

        for peer in self.peers.values():
            if peer.yearly_message_count is None:
                continue

            delay = peer.message_delay
            if delay is None:
                await asyncio.sleep(peer.next_idle_sleep(sleep_mean, sleep_std))
                continue

            message = peer.build_relay_request(delay, min_delay)
            await queue.put(message)
            await asyncio.sleep(delay * message.batch_size)
