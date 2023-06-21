import logging
import aiohttp

import asyncio
from ct.hopr_node import HOPRNode, formalin, connectguard

log = logging.getLogger(__name__)



class NetWatcher(HOPRNode):
    """ Class description."""
    def __init__(self, url: str, key: str):
        """
        Initialisation of the class.
        """
        super().__init__(url, key, 10, '.')
    

    @formalin(sleep=20)
    @connectguard
    async def transmit_peers(self, mocked: str = True):
        """
        Sends the detected peers to the Aggregator
        """
        log.info("Transmitting peers to Aggregator")
        url = "http://localhost:8080/lists"

        if not mocked:
            async with aiohttp.ClientSession() as session:
                data = {"foo": ["0x12", 12]}
                async with session.post(url, data) as response:
                    data = await response.text()
                    print(data)

        sent_list = [p[-5:] for p in self.peers]
        log.info(f"Transmisted peers: {', '.join(sent_list)}")
        self.peers.clear()
        

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info("Starting node")
        if self.tasks:
            return
    
        self.started = True
        self.tasks.add(asyncio.create_task(self.connect(address="hopr")))
        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))
        await asyncio.gather(*self.tasks)

    def __str__(self):
        return