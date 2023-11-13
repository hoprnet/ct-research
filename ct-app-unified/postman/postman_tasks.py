import asyncio
import logging
import random
import time
from enum import Enum

from celery import Celery
from core.components.horpd_api import HoprdAPI
from core.components.utils import Utils

log = logging.getLogger()
log.setLevel(logging.INFO)


app = Celery(
    name=Utils.envvar("PROJECT_NAME"), broker=Utils.envvar("CELERY_BROKER_URL")
)
app.autodiscover_tasks(force=True)


class TaskStatus(Enum):
    """
    Enum to represent the status of a task. This status is also used when creating a
    task in the outgoing queue.
    """

    DEFAULT = "DEFAULT"
    SUCCESS = "SUCCESS"
    RETRIED = "RETRIED"
    SPLITTED = "SPLITTED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


async def channel_balance(api: HoprdAPI, src_peer_id: str, dest_peer_id: str) -> float:
    """
    Get the channel balance of a given address.
    :param api: API helper instance.
    :param src_peer_id: Source channel peer id.
    :param dest_peer_id: Destination channel peer id.
    :return: Channel balance of the address.
    """
    channels = await api.all_channels(False)

    channel = [
        c
        for c in channels.all
        if c.destination_peer_id == dest_peer_id and c.source_peer_id == src_peer_id
    ]

    if len(channel) == 0:
        return 0
    else:
        return int(channel[0].balance) / 1e18


def create_batches(total_count, batch_size):
    if total_count < 0:
        return []

    full_batches = total_count // batch_size
    remainder = total_count % batch_size

    batches: list = [batch_size] * full_batches + [remainder] * bool(remainder)

    return batches


async def send_messages_in_batches(
    api: HoprdAPI,
    relayer: str,
    expected_count: int,
    recipient: str,
    timestamp: float,
    batch_size: int,
):
    relayed_count = 0
    issued_count = 0

    batches = create_batches(expected_count, batch_size)

    for batch_index, batch in enumerate(batches):
        for message_index in range(batch):
            # node is reachable, messages can be sent
            global_index = message_index + batch_index * batch_size

            issued_count += await api.send_message(
                recipient,
                f"From CT: distribution to {relayer} at {timestamp}-"
                f"{global_index + 1}/{expected_count}",
                [relayer],
            )
            await asyncio.sleep(Utils.envvar("DELAY_BETWEEN_TWO_MESSAGES", float))

        await asyncio.sleep(Utils.envvar("MESSAGE_DELIVERY_TIMEOUT", float))

        messages = await api.messages_pop_all(0x0320)
        relayed_count += len(messages)

    return relayed_count, issued_count


@app.task(name="send_1_hop_message")
def send_1_hop_message(
    peer: str,
    expected: int,
    ticket_price: float,
    timestamp: float = None,
    attempts: int = 0,
):
    """
    Celery task to send `messages_count` 1-hop messages to a peer. This method is the
    entry point for the celery worker. As the task that is executed
    relies on asyncio, we need to run it in a dedicated event loop. The only call this
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param expected: Number of messages to send.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    :param attempts: Number of attempts to send the message regardless of the node.
    """
    if timestamp is None:
        timestamp = time.time()

    send_status, node_peer_id, (issued, relayed) = asyncio.run(
        async_send_1_hop_message(
            peer,
            expected,
            ticket_price,
            timestamp,
        )
    )

    attempts += send_status in [TaskStatus.SPLITTED, TaskStatus.SUCCESS]

    if attempts >= Utils.envvar("MAX_ATTEMPTS", int):
        send_status = TaskStatus.TIMEOUT

    if send_status in [TaskStatus.RETRIED, TaskStatus.SPLITTED]:
        expected = expected - relayed
        Utils.taskSendMessage(app, peer, expected, ticket_price, timestamp, attempts)

    # store results in database
    if send_status != TaskStatus.RETRIED:
        Utils.taskStoreFeedback(
            app,
            peer,
            node_peer_id,
            expected,
            issued,
            relayed,
            send_status.value,
            timestamp,
        )


async def async_send_1_hop_message(
    peer_id: str,
    expected_count: int,
    ticket_price: float,
    timestamp: float,
) -> tuple[TaskStatus, tuple]:
    """
    Celery task to send `count` 1-hop messages to a peer in an async manner. A timeout
    mecanism is implemented to stop the task if sending a given bunch of messages takes
    too long.
    :param peer_id: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    :param attempts: Number of attempts to send the message regardless of the node.
    """

    # pick a random node and test connection
    addresses, key = Utils.nodesAddresses("NODE_ADDRESS_", "NODE_KEY")
    api = HoprdAPI(random.choice(addresses), key)

    node_peer_id = api.get_address("hopr")

    if node_peer_id is None:
        log.error("Can't connect to the node")
        return TaskStatus.RETRIED, None, (0, 0)
    else:
        log.info(f"Node peer id: {node_peer_id}")

    # validate balance of peer
    balance = await channel_balance(api, node_peer_id, peer_id)
    max_possible = min(expected_count, balance // ticket_price)

    if max_possible == 0:
        log.error(f"Balance of {peer_id} doesn't allow to send any message")
        return TaskStatus.RETRIED, node_peer_id, (0, 0)

    relayed, issued = await send_messages_in_batches(
        api,
        peer_id,
        max_possible,
        node_peer_id,
        timestamp,
        Utils.envvar("BATCH_SIZE", int),
    )

    status = TaskStatus.SUCCESS if relayed == expected_count else TaskStatus.SPLITTED

    log.info(
        f"From {node_peer_id} through {peer_id}: relayed {relayed}/{expected_count} (possible: {max_possible})"
    )

    return status, node_peer_id, (issued, relayed)


@app.task(name="fake_task")
def fake_task(
    peer: str,
    expected: int,
    ticket_price: float,
    timestamp: float = None,
    attempts: int = 0,
) -> TaskStatus:
    """
    Fake celery task to test if queues are working as expected.
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param expected: Number of messages to send.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    :param attempts: Number of attempts to send the message regardless of the node.
    """

    if timestamp is None:
        timestamp = time.time()

    log.info(f"Fake task execution started at {timestamp}")
    log.info(f"{expected} messages ment to be sent to {peer}")

    issued = random.randint(1, expected)
    relayed = random.randint(0, issued)

    Utils.taskStoreFeedback(
        app,
        peer,
        "fake_node",
        expected,
        issued,
        relayed,
        TaskStatus.SUCCESS.value,
        timestamp,
    )
