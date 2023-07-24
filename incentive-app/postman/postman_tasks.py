import asyncio
import logging

from celery import Celery

from tools import HoprdAPIHelper, envvar

log = logging.getLogger(__name__)


app = Celery(
    name=envvar("PROJECT_NAME"),
    broker=envvar("CELERY_BROKER_URL"),
    backend=envvar("CELERY_RESULT_BACKEND"),
)


# the name of the task is the name of the "<task_name>.<worker_peer_id>"
@app.task(name=f"{envvar('TASK_NAME')}.{envvar('WORKER_PEER_ID')}")
def send_1_hop_message(peer: str, count: int, node_list: list[str], node_index: int):
    """
    Celery task to send `count`1-hop messages to a peer.
    This method is the entry point for the celery worker. As the task that is executed
    relies on asyncio, we need to run it in a decated event loop. The only call this
    method does is to run the async method `async_send_1_hop_message`.
    :param peer: Peer ID to send messages to.
    :param count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    """
    return asyncio.run(async_send_1_hop_message(peer, count, node_list, node_index))


async def async_send_1_hop_message(
    peer_id: str, count: int, node_list: list[str], node_index: int
):
    """
    Celery task to send `count`1-hop messages to a peer in an async manner.
    :param peer_id: Peer ID to send messages to.
    :param count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    """

    api_host = envvar("API_HOST")
    api_token = envvar("API_TOKEN")

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
        log.error("Could not get connect to node. Trying with a backup node")

        # if there are no more nodes in the list, the task is stopped
        if node_index == len(node_list) - 1:
            log.info("This is the last node in the list, stopping")
            return "FAIL"

        node_index += 1
        node_id = node_list[node_index]
        log.info(f"Redirecting task to {node_id} (#{node_index} - {api_host})")

        app.send_task(
            f"{envvar('TASK_NAME')}.{node_id}",
            args=(peer_id, count, node_list, node_index),
            queue=node_id,
        )

        return "RETRYING"

    log.info(
        f"Sending {count} messages to `{peer_id}` "
        + f"via {node_list[node_index]}(#{node_index} - {api_host})"
    )

    # node is reachable, messages can be sent
    # TODO - SEND_MESSAGES_HERE
    await api.send_message(address, "dummy message", [peer_id])

    log.info(
        f"{count} messages sent to `{peer_id}` "
        + f"via {node_list[node_index]}(#{node_index} - {api_host})"
    )

    return "SUCCESS"
