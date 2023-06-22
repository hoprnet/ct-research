import asyncio
import functools
import logging
import uuid
from datetime import datetime, timedelta

import aiohttp

from ct.hopr_node import HOPRNode, connectguard

log = logging.getLogger(__name__)


def wakeupcall(message:str=None, minutes:int=0, seconds:int=0):
    """
    Decorator to log the start of a function, make it run until stopped, and delay the
    next iteration. The delay is calculated so that the function is triggered every 
    whole `minutes`min and `seconds`sec.
    :param message: the message to log when the function starts
    :param minutes: next whole minute to trigger the function
    :param seconds: next whole second to trigger the function
    """

    def next_delay_in_seconds(minutes: int = 0, seconds: int = 0):
        delta = timedelta(minutes=minutes, seconds=seconds)
        if delta.seconds == 0:
            return 0
        
        dt = datetime.now()
        min_date = datetime.min
        next_time = min_date + round((dt - min_date) / delta + 0.5) * delta
        return round((next_time - dt).total_seconds())

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            await asyncio.sleep(5)
            
            if message is not None:
                log.info(message)

            while self.started:
                await func(self, *args, **kwargs)

                sleep = next_delay_in_seconds(minutes=minutes, seconds=seconds)
                if sleep != 0:
                    await asyncio.sleep(sleep)

        return wrapper
    return decorator

class NetWatcher(HOPRNode):
    """ Class description."""
    def __init__(self, url: str, key: str, posturl: str):
        """
        Initialisation of the class.
        """
        # assign unique uuid as a string
        self.id = str(uuid.uuid4())
        self.posturl = posturl
        self.session = aiohttp.ClientSession()
        
        super().__init__(url, key, 10, '.')
    

    def wipe_peers(self):
        """
        Wipes the list of peers
        """
        log.info("Wiping peers")

        self.peers.clear()

    async def _post_list(self, session, peer_list: list):
        """
        Sends the detected peers to the Aggregator
        """
        short_list = [p[-5:] for p in peer_list]
        data = {"id": self.id, "list": list(short_list)}

        async with session.post(self.posturl, json=data) as response:
            if response.status == 200:
                log.info(f"Transmisted peers: {', '.join(short_list)}")
            else:
                log.error(f"Error transmitting peers: {response.status}")

    @wakeupcall(seconds=30)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        log.info("Transmitting peers")

        async with aiohttp.ClientSession() as session:
            await self._post_list(session, self.peers)

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
        self.tasks.add(asyncio.create_task(self.transmit_peers()))
        await asyncio.gather(*self.tasks)

    def __str__(self):
        return