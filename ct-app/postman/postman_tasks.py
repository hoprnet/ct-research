import asyncio
import logging
import random
import time
from enum import Enum

from celery import Celery

from tools import HoprdAPIHelper, envvar, getlogger

log = getlogger()
log.setLevel(logging.INFO)


class TaskStatus(Enum):
    """
    Enum to represent the status of a task. This status is also used when creating a
    task in the outgoing queue.
    """

    DEFAULT = "DEFAULT"
    SUCCESS = "SUCCESS"
    RETRIED = "RETRIED"
    SPLITTED = "SPLITTED"
    LEFTOVERS = "LEFTOVERS"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


app = Celery(name=envvar("PROJECT_NAME"), broker=envvar("CELERY_BROKER_URL"))
app.autodiscover_tasks(force=True)


async def channel_balance(
    api: HoprdAPIHelper, src_peer_id: str, dest_peer_id: str
) -> float:
    """
    Get the channel balance of a given address.
    :param api: API helper instance.
    :param src_peer_id: Source channel peer id.
    :param dest_peer_id: Destination channel peer id.
    :return: Channel balance of the address.
    """
    channels = await api.all_channels(False)

    channel = list(
        filter(
            lambda c: c.destination_peer_id == dest_peer_id
            and c.source_peer_id == src_peer_id,
            channels,
        )
    )

    if len(channel) == 0:
        return 0
    else:
        return int(channel[0].balance) / 1e18


def loop_through_nodes(node_list: list[str], node_index: int) -> tuple[str, int]:
    """
    Get the next node address in the list of nodes. If the index is out of bounds, it
    will be reset to 0.
    :param node_list: List of nodes to loop through.
    :param node_index: Index of the current node.
    :return: Tuple containing the next node address and the next node index.
    """
    node_index = (node_index + 1) % len(node_list)

    return node_list[node_index], node_index


def create_batches(total_count, batch_size):
    if total_count < 0:
        return []

    full_batches = total_count // batch_size
    remainder = total_count % batch_size

    batches: list = [batch_size] * full_batches + [remainder] * bool(remainder)

    return batches


async def send_messages_in_batches(
    api: HoprdAPIHelper,
    peer_id: str,
    expected_count: int,
    address: str,
    timestamp: float,
    batch_size: int,
):
    effective_count = 0
    issued_count = 0

    batches = create_batches(expected_count, batch_size)

    for batch_index, batch in enumerate(batches):
        for message_index in range(batch):
            # node is reachable, messages can be sent
            global_index = message_index + batch_index * batch_size

            issued_count += await api.send_message(
                address,
                f"From CT: distribution to {peer_id} at {timestamp}-"
                f"{global_index + 1}/{expected_count}",
                [peer_id],
            )
            await asyncio.sleep(envvar("DELAY_BETWEEN_TWO_MESSAGES", float))

        await asyncio.sleep(envvar("MESSAGE_DELIVERY_TIMEOUT", float))

        messages = await api.messages_pop_all(0x0320)
        effective_count += len(messages)

    return effective_count, issued_count


@app.task(name="send_1_hop_message")
def send_1_hop_message(
    peer: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    ticket_price: float,
    timestamp: float = None,
    attempts: int = 0,
) -> TaskStatus:
    """
    Celery task to send `messages_count` 1-hop messages to a peer. This method is the
    entry point for the celery worker. As the task that is executed
    relies on asyncio, we need to run it in a dedicated event loop. The only call this
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    :param attempts: Number of attempts to send the message regardless of the node.
    """
    if timestamp is None:
        timestamp = time.time()

    return asyncio.run(
        async_send_1_hop_message(
            peer,
            expected_count,
            node_list,
            node_index,
            ticket_price,
            timestamp,
            attempts,
        )
    )


async def async_send_1_hop_message(
    peer_id: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    ticket_price: float,
    timestamp: float,
    attempts: int,
) -> TaskStatus:
    """
    Celery task to send `count` 1-hop messages to a peer in an async manner. A timeout
    mecanism is implemented to stop the task if sending a given bunch of messages takes
    too long.
    :param peer_id: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    :param attempts: Number of attempts to send the message regardless of the node.
    """

    # at the first iteration, the number of attempts is set to 0. At each task
    # transfer, the method will check if the counter is still acceptable to consider
    # trying to send a message
    max_attempts = envvar("MAXATTEMPTS", int)
    if attempts >= max_attempts:
        log.error(f"Trying to send a message more than {max_attempts}x, stopping")
        return TaskStatus.TIMEOUT, TaskStatus.DEFAULT

    attempts += 1

    # initialize the API helper and task status
    api_host = envvar("API_HOST")
    api_key = envvar("API_KEY")
    status = TaskStatus.DEFAULT
    feedback_status = TaskStatus.DEFAULT

    effective_count = 0
    issued_count = 0
    already_in_inbox = 0

    api = HoprdAPIHelper(api_host, api_key)

    # try to connect to the node. If the `get_address` method fails, it means that the
    # node is not reachable
    try:
        own_peer_id = await api.get_address("hopr")
    except Exception:
        log.error("Could not get peer id from API")
        own_peer_id = None
    else:
        log.info(f"Got peer id: {own_peer_id}")

    # if the node is not reachable, the task is tranfered to the next node in the list
    if own_peer_id is None:
        log.error("Could not connect to node. Transfering task to the next node.")
        status = TaskStatus.RETRIED
    else:
        inbox = await api.messages_pop_all(0x0320)
        already_in_inbox = len(inbox)

        balance = await channel_balance(api, own_peer_id, peer_id)

        possible_count = min(expected_count, balance // ticket_price)

        if possible_count < expected_count:
            log.warning(
                "Insufficient balance to send all messages at once "
                + f"(balance: {balance}, "
                + f"count: {expected_count}, "
                + f"ticket price: {ticket_price})"
            )

        if possible_count > 0:
            effective_count, issued_count = await send_messages_in_batches(
                api,
                peer_id,
                possible_count,
                own_peer_id,
                timestamp,
                envvar("BATCH_SIZE", int),
            )

        if effective_count >= expected_count:
            status = TaskStatus.SUCCESS
        else:
            status = TaskStatus.SPLITTED

    log.info(
        f"{effective_count}/{expected_count} messages sent to `{peer_id}` via "
        + f"{own_peer_id} ({api_host})"
    )
    if already_in_inbox > 0:
        log.warning(f"{already_in_inbox} messages were already in the inbox")

    if status != TaskStatus.SUCCESS:
        node_address, node_index = loop_through_nodes(node_list, node_index)
        message_count = expected_count - effective_count
        log.info(f"Creating task for {node_address} to send {message_count} messages.")

        try:
            app.send_task(
                "send_1_hop_message",
                args=(
                    peer_id,
                    message_count,
                    node_list,
                    node_index,
                    timestamp,
                    attempts,
                ),
                queue=node_address,
            )
        except Exception:
            # shoud never happen. If it does, it means that the targeted queue is not up
            log.exception("Could not send task")

    try:
        app.send_task(
            "feedback_task",
            args=(
                peer_id,
                own_peer_id,
                effective_count,
                expected_count,
                status.value,
                timestamp,
                issued_count,
            ),
            queue="feedback",
        )
        if already_in_inbox > 0:
            app.send_task(
                "feedback_task",
                args=(
                    peer_id,
                    own_peer_id,
                    already_in_inbox,
                    0,
                    TaskStatus.LEFTOVERS.value,
                    timestamp,
                    0,
                ),
                queue="feedback",
            )
    except Exception:
        # shoud never happen. If it does, it means that the targeted queue is not up
        log.exception("Could not send feedback task")
        feedback_status = TaskStatus.FAILED
    else:
        feedback_status = TaskStatus.SUCCESS

    return status, feedback_status


@app.task(name="fake_task")
def fake_task(
    peer: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    ticket_price: float,
    timestamp: float = None,
) -> TaskStatus:
    """
    Fake celery task to test if queues are working as expected.
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    :param ticket_price: Cost of sending a message.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    """

    if timestamp is None:
        timestamp = time.time()

    log.info(f"Fake task execution started at {timestamp}")
    log.info(f"{expected_count} messages ment to be sent to {peer}")
    log.info(f"Node list: {node_list} (starting at index {node_index})")

    app.send_task(
        "feedback_task",
        args=(
            peer,
            node_list[node_index],
            random.randint(0, expected_count),
            expected_count,
            TaskStatus.SUCCESS.value,
            timestamp,
        ),
        queue="feedback",
    )
