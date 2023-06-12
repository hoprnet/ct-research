import asyncio
import logging
import random
import traceback
import numpy as np

from pathlib import Path

from viz import network_viz

from .throttle_api import ThrottledHoprdAPI

log = logging.getLogger(__name__)

class HOPRNode:
    """
    Implements the functionality of a HOPR node through the hoprd-api-python and WebSocket
    """

    def __init__(self, url: str, key: str, max_lat_count: int = 100, log_folder: str = "."):
        """
        :returns: a new instance of a HOPR node using 'url' and API 'key'
        """
        self.api_key = key
        self.url = url
        self.peer_id = None

        # access the functionality of the hoprd python api
        self.api = ThrottledHoprdAPI(url=url, token=key)

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dictionary to keep the self.max_lat_count latency measures {peer: np.array([latency, latency, ...])}
        self.latency = dict[str, np.ndarray]()
        self.max_lat_count = max_lat_count

        # a folder to store the logs
        self.log_folder = Path(log_folder)
        self.log_folder.mkdir(parents=True, exist_ok=True)

        # a set to keep track of the running tasks
        self.tasks = set()
        self.started = False
        log.debug("Created HOPR node instance")

    async def connect(self):
        """
        Connects to this HOPR node, returning its peer_id.
        """
        address = "hopr"

        log.debug("Connecting to node")
        while self.started:
            try:
                response = await self.api.get_address()
            except Exception as e:
                self.peer_id = None
                log.error(f"Could not connect to {self.api.url}: {e}")
                log.error(traceback.format_exc())
            else:
                json_body = response.json()
                if address in json_body:
                    self.peer_id = json_body[address]
                    log.info(f"HOPR node {self.peer_id} is up")
                else:
                    self.peer_id = None
                    log.info("HOPR node is down")
            finally:
                await asyncio.sleep(5)

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
        if self.connected:
            self.peer_id = None
            log.info("Disconnected HOPR node")

    async def gather_peers(self):
        """
        Long-running task that continously updates the set of peers connected to this node.
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """
        status = "connected"
        connection_quality = 1

        while self.started:
            # check that we are still connected
            if not self.connected:
                log.debug("gather_peers() waiting for connection")
                await asyncio.sleep(1)
                continue

            try:
                response = await self.api.peers(quality=connection_quality)

            except Exception as e:
                log.error(f"Could not get peers from {self.api.url}: {e}")
                log.error(traceback.format_exc())
            else:
                json_body = response.json()
                if status not in json_body:
                    continue
            
                for peer in json_body[status]:
                    peer_id = peer["peerId"]
                    if peer_id in self.peers:
                        continue

                    self.peers.add(peer_id)
                    log.info(f"Found new peer {peer_id}")

                await asyncio.sleep(5)

    async def plot(self):
        """
        Long-running task that regularly plots the network and latencies amont its nodes.

        :returns: nothing; throws expection in case of error
        """
        i = 0
        while self.started:
            await asyncio.sleep(30)
            
            if not self.connected or self.latency is None:
                continue
        
            i += 1
            file_name = self.log_folder.joinpath(f"net_viz-{i:04d}")
            log.info(f"Creating visualization [ {file_name} ]")
            try:
                await asyncio.to_thread(
                    network_viz, {self.peer_id: self.latency}, file_name
                )
            except Exception as e:
                log.error(f"Could not create visualization [ {file_name} ]: {e}")
                log.error(traceback.format_exc())

    async def ping_peers(self):
        """
        Long-running task that pings the peers of this node and
        records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a NumPy array of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.

        :returns: nothing
        """

        while self.started:
            # check that we are still connected, avoiding full CPU usage
            await asyncio.sleep(1)
            if not self.connected:
                log.debug("ping_peers() waiting for connection")
                continue

            # randomly sample the peer set to converge towards
            # a uniform distribution of pings among peers
            sampled_peers = random.sample(sorted(self.peers), len(self.peers)) 
            # TODO; Necessary ?
            
            # create an array to keep the latency measures of new peers
            for peer_id in sampled_peers:
                if peer_id not in self.latency.keys():
                    self.latency[peer_id] = np.array([])
            # TODO: necessary ?
            
            for peer_id in sampled_peers:

                measured_latency = await self.api.ping(peer_id)
                latency = measured_latency if measured_latency is not None else np.nan

                # add the latency measure to the array of the peer
                self.latency[peer_id] = np.append(self.latency[peer_id], latency)
                self.latency[peer_id] = self.latency[peer_id][-self.max_lat_count:]
                
                # throttle the API requests towards the node
                if not self.connected:
                    break
                else:
                    await asyncio.sleep(5)

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info("Starting node")
        if len(self.tasks) != 0:
            return
    
        self.started = True
        self.tasks.add(asyncio.create_task(self.connect()))
        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.plot()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the running tasks of this node
        """
        log.info("Stopping node")
        self.started = False

        self.disconnect()

        for t in self.tasks:
            t.add_done_callback(self.tasks.discard)

        asyncio.gather(*self.tasks)
