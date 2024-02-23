import asyncio
import logging
import time
from datetime import datetime

from billiard import current_process
from celery import Celery
from core.components.hoprd_api import HoprdAPI
from core.components.parameters import Parameters
from core.components.utils import Utils
from database import DatabaseConnection, Reward

from .task_status import TaskStatus
from .utils import Utils as PMUtils

log = logging.getLogger()
log.setLevel(logging.INFO)

params = Parameters()("PARAM_", "RABBITMQ_")

if not Utils.checkRequiredEnvVar("postman"):
    exit(1)

app = Celery(
    name=params.rabbitmq.project_name,
    broker=f"amqp://{params.rabbitmq.username}:{params.rabbitmq.password}@{params.rabbitmq.host}/{params.rabbitmq.virtualhost}",
)
app.autodiscover_tasks(force=True)


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
        async_send_1_hop_message(peer, expected, ticket_price, timestamp)
    )

    attempts += 1  # send_status in [TaskStatus.SPLITTED, TaskStatus.SUCCESS]

    if attempts >= params.param.max_attempts:
        send_status = TaskStatus.TIMEOUT

    if send_status in [TaskStatus.RETRIED, TaskStatus.SPLIT]:
        Utils.taskSendMessage(
            app, peer, expected - relayed, ticket_price, timestamp, attempts
        )

    # store results in database
    if send_status != TaskStatus.RETRIED:
        with DatabaseConnection() as session:
            entry = Reward(
                peer_id=peer,
                node_address=node_peer_id,
                expected_count=expected,
                effective_count=relayed,
                status=send_status.value,
                timestamp=datetime.fromtimestamp(timestamp),
                issued_count=issued,
            )

            session.add(entry)
            session.commit()

            log.debug(f"Stored reward entry in database: {entry}")

    return send_status


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

    # pick the associated node
    address = Utils.envvar(f"NODE_ADDRESS_{current_process().index+1}")
    key = Utils.envvar(f"NODE_KEY_{current_process().index+1}")
    api = HoprdAPI(address, key)

    node_peer_id = await api.get_address("hopr")

    if node_peer_id is None:
        log.error("Can't connect to the node")
        return TaskStatus.RETRIED, None, (0, 0)
    else:
        log.info(f"Node peer id: {node_peer_id}")

    # validate balance of peer
    balance = await api.channel_balance(node_peer_id, peer_id)
    print(
        f"Should send {expected_count} messages to {peer_id} with balance {balance=} (ticket price: {ticket_price})"
    )
    max_possible = min(expected_count, balance // ticket_price)

    if max_possible == 0:
        log.error(f"Balance of {peer_id} doesn't allow to send any message")
        return TaskStatus.RETRIED, node_peer_id, (0, 0)

    relayed, issued = await PMUtils.send_messages_in_batches(
        api,
        peer_id,
        max_possible,
        node_peer_id,
        timestamp,
        params.param.batch_size,
        params.param.delay_between_two_messages,
        params.param.message_delivery_timeout,
    )

    status = TaskStatus.SPLIT if relayed < expected_count else TaskStatus.SUCCESS

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

    address = Utils.envvar(f"NODE_ADDRESS_{current_process().index+1}")

    log.info(f"Fake task execution started at {timestamp}")
    log.info(f"{expected} messages ment to be sent through {peer} by {address}")

    Utils.taskStoreFeedback(
        app,
        peer,
        "fake_node",
        expected,
        0,
        0,
        TaskStatus.SUCCESS.value,
        timestamp,
    )
