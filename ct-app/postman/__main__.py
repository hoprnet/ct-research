import asyncio

from tools import HoprdAPIHelper, envvar, getlogger

log = getlogger()


async def retrieve_address():
    """
    Celery task to send `count`1-hop messages to a peer in an async manner.
    :param peer_id: Peer ID to send messages to.
    :param count: Number of messages to send.
    :param node_list: List of nodes connected to this peer, they can serve as backups.
    :param node_index: Index of the node in the list of nodes.
    """
    try:
        api_host = envvar("API_HOST")
        api_token = envvar("API_KEY")
    except ValueError:
        log.exception("Could not get API_HOST or API_KEY from environment")
        return None

    api = HoprdAPIHelper(api_host, api_token)

    # try to connect to the node. If the `get_address` method fails, it means that the
    # node is not reachable
    try:
        address = await api.get_address("hopr")
    except Exception:
        log.error("Could not get address from API")
        address = None

    return address


if __name__ == "__main__":
    address = asyncio.run(retrieve_address())

    exit(address)
