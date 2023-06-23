import asyncio
import logging
import uuid

from aiohttp.client_exceptions import ClientConnectorError
from aiohttp import ClientSession
from ct.hopr_node import HOPRNode, connectguard

from ct.decorator import wakeupcall

log = logging.getLogger(__name__)

class NetWatcher(HOPRNode):
    """
    NetWatcher implementation. This class is used to detect peers and send them to the 
    Aggregator via a POST request.
    """
    def __init__(self, url: str, key: str, posturl: str):
        """
        Initialisation of the class.
        :param url: the url of the hopr node
        :param key: the key of the hopr node
        :param posturl: the url of the Aggregator to send the peers to
        """
        # assign unique uuid as a string
        self.id = str(uuid.uuid4())
        self.posturl = posturl
        self.session = ClientSession()
        
        super().__init__(url, key, 10, '.')
    

    def wipe_peers(self):
        """
        Wipes the list of peers
        """
        log.info("Wiping peers")

        self.peers.clear()

    async def _post_list(self, session: ClientSession, peers: list, latencies: list):
        """
        Sends the detected peers to the Aggregator. For the moment, only the last 
        latency is transmitted for each peer.
        :param session: the aiohttp session
        :param peers: the list of peers
        :param latencies: the list of latencies
        """

        # list of shorten peer ids (only for convenience. will be removed)
        short_list = [p[-5:] for p in peers] 

        # list standard peer ids (creating a secure copy of the list)
        long_list = [p for p in peers]

        latency_dict = {}
        for i in range(len(short_list)):
            latency = latencies[long_list[i]][-1] if long_list[i] in latencies else None
            
            latency_dict[short_list[i]] = latency

        data = {"id": self.id, "list": latency_dict}

        try:
            async with session.post(self.posturl, json=data) as response:
                if response.status == 200:
                    log.info(f"Transmisted peers: {', '.join(short_list)}")
        except ClientConnectorError as e:
            log.error(f"Error transmitting peers: {e}")

    @wakeupcall(message="Initiated peers transmission", minutes=1)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        async with ClientSession() as session:
            await self._post_list(session, self.peers, self.latency)

        self.wipe_peers()
    
    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info(f"Starting instance '{self.id}'")
        if self.tasks:
            return
    
        self.started = True
        self.tasks.add(asyncio.create_task(self.connect(address="hopr")))
        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))

        await asyncio.gather(*self.tasks)

    def __str__(self):
        return