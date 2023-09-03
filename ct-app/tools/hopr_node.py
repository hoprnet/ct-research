import asyncio

from .decorator import formalin
from .hopr_api_helper import HoprdAPIHelper
from .utils import getlogger

log = getlogger()


class HOPRNode:
    """
    Implements the functionality of a HOPR node through the hoprd-api-python
    """

    def __init__(self, url: str, key: str):
        """
        :param url: the url of the HOPR node
        :param key: the API key of the HOPR node
        :param max_lat_count: the maximum number of latency measures to keep
        :param plot_folder: the folder to store the plots
        :returns: a new instance of a HOPR node using 'url' and API 'key'
        """
        self.api_key = key
        self.url = url
        self.peer_id = None

        # access the functionality of the hoprd python api
        self.api = HoprdAPIHelper(url=url, token=key)

        # a set to keep track of the running tasks
        self.tasks = set[asyncio.Task]()
        self.started = False
        log.debug("Created HOPR node instance")

    @property
    def connected(self) -> bool:
        """
        :returns: True if this node is connected, False otherwise.
        """
        return self.peer_id is not None

    def disconnect(self):
        """
        Placeholder for class cleanup

        :returns: nothing
        """
        if not self.connected:
            return

        self.peer_id = None
        log.info("Disconnected HOPR node")

    @formalin(message="Connecting to node", sleep=20)
    async def connect(self, address: str = "hopr"):
        """
        Connects to this HOPR node and sets the peer_id of this instance.
        :param address: the address of the HOPR node to connect to
        :returns: nothing
        """

        self.peer_id = await self.api.get_address(address)

        if self.peer_id is None:
            log.info("HOPR node is down")
        else:
            log.info(f"HOPR node {self.peer_id} is up")
