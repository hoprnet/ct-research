import functools
import logging
import aiohttp

import asyncio
from ct.hopr_node import HOPRNode

log = logging.getLogger(__name__)


def formalin(message: str = None, sleep: int = None):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration
    :param message: the message to log when the function starts
    :param sleep: the duration to sleep after an interation
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if message is not None:
                log.info(message)

            while self.started:
                await func(self, *args, **kwargs)

                if sleep is not None:
                    await asyncio.sleep(sleep)

        return wrapper
    return decorator

def connectguard(func):
    """
    Decorator to check if the node is connected before running anything
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self.connected:
            log.warning("Node not connected, skipping")
            return

        await func(self, *args, **kwargs)

    return wrapper

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
        url = "http://localhost:3000/ct/fin_dist/aggregator/send_list"

        if not mocked:
            async with aiohttp.ClientSession() as session:
                data = {"terms": 1, "captcha": 1}
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