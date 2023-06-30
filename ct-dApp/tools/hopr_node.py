import asyncio
import logging
import random


from .hopr_api_helper import HoprdAPIHelper

from .decorator import formalin, connectguard

log = logging.getLogger(__name__)

class HOPRNode:
    """
    Implements the functionality of a HOPR node through the hoprd-api-python and WebSocket
    """

    def __init__(self, url: str, key: str, max_lat_count: int = 100):
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

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dict to keep the max_lat_count latency measures {peer: [51, 23, ...]}
        self.latency = dict[str, list]()
        self.max_lat_count = max_lat_count

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

        try:
            self.peer_id = await self.api.get_address(address)
        except Exception as e:
            log.warning(f"Could not connect to {self.api.url}: {e}")
            
        if self.peer_id is None:
            log.info("HOPR node is down")
        else:
            log.info(f"HOPR node {self.peer_id[-5:]} is up")

    @formalin(message="Gathering peers", sleep=30)
    @connectguard
    async def gather_peers(self, quality: float = 1.0):
        """
        Long-running task that continously updates the set of peers connected to this 
        node.
        :param quality: 
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        found_peers = await self.api.peers(param="peerId", quality=quality)
        
        if found_peers:
            new_peers = set(found_peers) - set(self.peers)
            vanished_peers = set(self.peers) - set(found_peers)

            for peer in new_peers:            
                self.peers.add(peer)
                log.info(f"Found new peer {peer[-5:]}")

            for peer in vanished_peers:
                log.info(f"Peer {peer[-5:]} vanished")


    @formalin(message="Pinging peers", sleep=10.0)
    @connectguard
    async def ping_peers(self):
        """
        Pings the peers of this node and records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a list of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.
        """

        # shuffle the peer set to converge towards a uniform distribution of pings among
        # peers
        sampled_peers = random.sample(sorted(self.peers), len(self.peers))
        
        # create an array to keep the latency measures of new peers
        for peer_id in sampled_peers:
            if peer_id not in self.latency:
                self.latency[peer_id] = []
        
        for peer_id in sampled_peers:
            if not self.connected:
                break
            else:                                   
                await asyncio.sleep(0.1) 
            # Above delay is set to allow the second peer's pinging from the test file 
            # before timeout (defined by test method). Can be changed. 

            latency = await self.api.ping(peer_id, "latency")

            self.latency[peer_id].append(latency)
            self.latency[peer_id] = self.latency[peer_id][-self.max_lat_count:]