import asyncio
import functools
import logging
import uuid
from datetime import datetime, timedelta

import aiohttp
from aiohttp.client_exceptions import ClientConnectorError

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

        
        dt = datetime.now()
        min_date = datetime.min
        try:
            next_time = min_date + round((dt - min_date) / delta + 0.5) * delta
        except ZeroDivisionError:
            log.error("Next sleep is 0 seconds..")
            return 1
        
        delay = int((next_time - dt).total_seconds())
        if delay == 0:
            return delta.seconds
        return delay

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            if message is not None:
                log.info(message)

            sleep = next_delay_in_seconds(minutes=minutes, seconds=seconds)
            await asyncio.sleep(sleep)            

            while self.started:
                await func(self, *args, **kwargs)

                sleep = next_delay_in_seconds(minutes=minutes, seconds=seconds)
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

    async def _post_list(self, session, peers: list, latencies: list):
        """
        Sends the detected peers to the Aggregator
        """
        short_list = [p[-5:] for p in peers]
        long_list = [p for p in peers]


        latency_dict = {}
        for i in range(len(short_list)):
            if long_list[i] in latencies:
                latency = latencies[long_list[i]][-1]
            else:
                latency = None
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
        async with aiohttp.ClientSession() as session:
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