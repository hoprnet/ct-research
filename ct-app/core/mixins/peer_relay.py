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

        steps = self.send_plan_coordinator.build_steps(
            self.peers.values(),
            min_delay,
            sleep_mean,
            sleep_std,
        )
        for step in steps:
            if step.message is not None:
                await queue.put(step.message)
            await asyncio.sleep(step.sleep_seconds)
