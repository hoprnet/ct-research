import asyncio
import time
from enum import Enum

from celery import Celery

from tools import HoprdAPIHelper, envvar, getlogger

log = getlogger()


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


app = Celery(
    name=envvar("PROJECT_NAME"),
    broker=f"amqp://{envvar('RABBITMQ_USERNAME')}:{envvar('RABBITMQ_PASSWORD')}@{envvar('RABBITMQ_HOST')}/{envvar('RABBITMQ_VIRTUALHOST')}",
    # backend=envvar("CELERY_RESULT_BACKEND"),
)
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


# the name of the task is the name of the "<task_name>.<node_address>"
@app.task(name=f"{envvar('TASK_NAME')}.{envvar('NODE_ADDRESS')}")
def send_1_hop_message(
    peer: str,
    expected_count: int,
    node_list: list[str],
    node_index: int,
    timestamp: float = time.time(),
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
    if time.time() - timestamp > 60 * 60 * 2:  # timestamp is older than 2 hours
        log.error("Trying to send a message for more than 2 hours, stopping")
        return TaskStatus.TIMEOUT

    # initialize the API helper and task status
    api_host = envvar("API_HOST")
    api_token = envvar("API_TOKEN")
    status = TaskStatus.DEFAULT
    effective_count = 0

    api = HoprdAPIHelper(api_host, api_token)

    # try to connect to the node. If the `get_address` method fails, it means that the
    # node is not reachable
    try:
        address = await api.get_address("hopr")
    except Exception:
        log.error("Could not get address from API")
        address = None
    finally:
        log.info(f"Got address: {address}")

    # if the node is not reachable, the task is tranfered to the next node in the list
    if address is None:
        log.error("Could not connect to node. Transfering task to the next node.")
        status = TaskStatus.RETRIED

    while status == TaskStatus.DEFAULT:
        # node is reachable, messages can be sent
        successful_sending = await api.send_message(address, "foo", [peer_id])
        effective_count += successful_sending

        if not successful_sending:
            log.error(
                "Could not send message. Transfering remaining ones to the next node."
            )
            status = TaskStatus.SPLITTED

        if effective_count == expected_count:
            status = TaskStatus.SUCCESS

    log.info(
        f"{effective_count}/{expected_count} messages sent to `{peer_id}` via "
        + f"{address} ({api_host})"
    )

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

    if status != TaskStatus.SUCCESS:
        node_address, node_index = loop_through_nodes(node_list, node_index)
        log.info(
            f"Creating task for {node_address} to send {effective_count} messages."
        )

        app.send_task(
            f"{envvar('TASK_NAME')}.{node_address}",
            args=(
                peer_id,
                expected_count - effective_count,
                node_list,
                node_index,
                timestamp,
            ),
            queue=node_address,
        )

    return status
