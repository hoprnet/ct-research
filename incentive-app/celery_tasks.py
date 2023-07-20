import asyncio
import logging

from celery import Celery
from tools import HoprdAPIHelper, envvar

log = logging.getLogger(__name__)

PROJECT_NAME = envvar("PROJECT_NAME")
CELERY_BROKER_URL = envvar("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = envvar("CELERY_RESULT_BACKEND")

app = Celery(name=PROJECT_NAME, broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


@app.task(name=f"send_1_hop_message.{envvar('WORKER_PEER_ID')}")
def send_1_hop_message(peer: str, count: int):
    asyncio.run(async_send_1_hop_message(peer, count))


async def async_send_1_hop_message(peer: str, count: int):
    """
    Celery task to send `count`1-hop messages to a peer.
    :param peer: Peer ID to send messages to.
    :param count: Number of messages to send.
    """

    api_host = envvar("API_HOST")
    api_token = envvar("API_TOKEN")

    log.info(f"Sending {count} messages to `{peer}` via {api_host}.")

    api = HoprdAPIHelper(api_host, api_token)
    address = await api.get_address("hopr")

    if address is None:
        log.error("Could not get address from API.")
        # return

    for _ in range(count):
        print(f"Sending message to `{peer}`.")
