import asyncio

from prometheus_client import REGISTRY

from core.types.message_format import MessageFormat
from core.types.message_queue import QUEUE_SIZE, MessageQueue


def queue_size() -> int:
    """Current message queue depth, as reported by the `ct_queue_size` gauge."""
    return int(REGISTRY.get_sample_value("ct_queue_size") or 0)


def reset_queue_size() -> None:
    """Call when the `MessageQueue` singleton is discarded, so the gauge matches the new queue."""
    QUEUE_SIZE.set(0)


async def drain_queue() -> list[MessageFormat]:
    items = []
    while queue_size():
        try:
            items.append(await asyncio.wait_for(MessageQueue().get(), timeout=1.0))
        except TimeoutError:
            break
    return items
