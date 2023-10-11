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

    batches = create_batches(expected_count, batch_size)
    message_delivery_timeout = envvar("MESSAGE_DELIVERY_TIMEOUT", float)

    for batch_index, batch in enumerate(batches):
        for message_index in range(batch):
            # node is reachable, messages can be sent
            global_index = message_index + batch_index * batch_size

            await api.send_message(
                address,
                f"From CT: distribution to {peer_id} at {timestamp}-"
                f"{global_index + 1}/{expected_count}",
                [peer_id],
            )
            await asyncio.sleep(envvar("DELAY_BETWEEN_TWO_MESSAGES", float))

        await asyncio.sleep(message_delivery_timeout)

        messages = await api.messages_pop_all(0x0320)
        effective_count += len(messages)

    return effective_count


@app.task(name="send_1_hop_message")
def send_1_hop_message(
    peer: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    timestamp: float = None,
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
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    """
    if timestamp is None:
        timestamp = time.time()

    return asyncio.run(
        async_send_1_hop_message(peer, expected_count, node_list, node_index, timestamp)
    )


async def async_send_1_hop_message(
    peer_id: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    timestamp: float,
) -> TaskStatus:
    """
    Celery task to send `count` 1-hop messages to a peer in an async manner. A timeout
    mecanism is implemented to stop the task if sending a given bunch of messages takes
    too long.
    :param peer_id: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    :param timestamp: Timestamp at first iteration. For timeout purposes.
    """

    # at the first iteration, the timestamp is set to the current time. At each task
    # transfer, the method will check if the timestamp is recent enough to consider
    # trying to send a message
    timeout = envvar("TIMEOUT", int)
    if time.time() - timestamp > timeout:  # timestamp is older than timeout
        log.error(f"Trying to send a message for more than {timeout}s, stopping")
        return TaskStatus.TIMEOUT, TaskStatus.DEFAULT

    # initialize the API helper and task status
    api_host = envvar("API_HOST")
    api_key = envvar("API_KEY")
    status = TaskStatus.DEFAULT
    feedback_status = TaskStatus.DEFAULT

    effective_count = 0
    already_in_inbox = 0

    api = HoprdAPIHelper(api_host, api_key)

    # try to connect to the node. If the `get_address` method fails, it means that the
    # node is not reachable
    try:
        address = await api.get_address("hopr")
    except Exception:
        log.error("Could not get address from API")
        address = None
    else:
        log.info(f"Got address: {address}")

    # if the node is not reachable, the task is tranfered to the next node in the list
    if address is None:
        log.error("Could not connect to node. Transfering task to the next node.")
        status = TaskStatus.RETRIED
    else:
        inbox = await api.messages_pop_all(0x0320)
        already_in_inbox = len(inbox)
        effective_count = await send_messages_in_batches(
            api, peer_id, expected_count, address, timestamp, envvar("BATCH_SIZE", int)
        )

        if effective_count == expected_count:
            status = TaskStatus.SUCCESS
        else:
            status = TaskStatus.SPLITTED

    log.info(
        f"{effective_count}/{expected_count} messages sent to `{peer_id}` via "
        + f"{address} ({api_host})"
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
                address,
                effective_count,
                expected_count,
                status.value,
                timestamp,
            ),
            queue="feedback",
        )
        if already_in_inbox > 0:
            app.send_task(
                "feedback_task",
                args=(
                    peer_id,
                    address,
                    already_in_inbox,
                    0,
                    TaskStatus.LEFTOVERS.value,
                    timestamp,
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
    timestamp: float = None,
) -> TaskStatus:
    """
    Fake celery task to test if queues are working as expected.
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param expected_count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
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
