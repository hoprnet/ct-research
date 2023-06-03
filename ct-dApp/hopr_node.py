import asyncio
import logging
import random
import traceback

from hoprd import wrapper

from viz import network_viz

# pylint: disable=logging-format-interpolation,consider-using-f-string

log = logging.getLogger(__name__)


class HoprNode():
    """
    Implements the functionality of a HOPR node through its REST API and WebSocket
    """
    def __init__(self, url: str, key: str):
        """
        :returns: a new instance of a HOPR node using 'url' and API 'key'
        """
        self.api_key = key
        self.url     = url
        self.peer_id = None

        # access the functionality of the hoprd python api
        self.hoprd_api = wrapper.HoprdAPI(api_url=url, api_token=key)

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dictionary to keep the last 100 latency measures {peer: [latency, latency, ...]}
        self.latency = dict[str, list[int]]()

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
                response = await self.hoprd_api.get_address()
                json_body = response.json()
                if address in json_body:
                    self.peer_id = json_body[address]
                    log.info("HOPR node {} is up".format(self.peer_id))
                else:
                    self.peer_id = None
                    log.info("HOPR node is down")

            except Exception as exception:
                self.peer_id = None
                log.error("Could not connect to {}: {}".format(self.hoprd_api._api_url, str(exception)))
                log.error(traceback.format_exc())

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
        status= "connected"
        connection_quality= 1

        while self.started:
            # check that we are still connected
            if not self.connected:
                log.debug("gather_peers() waiting for connection")
                await asyncio.sleep(1)
                continue

            try:
                response = await self.hoprd_api.peers(quality=connection_quality)
                json_body = response.json()
                if status in json_body:
                    for peer in json_body[status]:
                        peer_id = peer["peerId"]
                        if peer_id not in self.peers:
                            self.peers.add(peer_id)
                            log.info("Found new peer {}".format(peer_id))
                await asyncio.sleep(5)

            except Exception as exception:
                log.error("Could not get peers from {}: {}".format(self.hoprd_api._api_url, str(exception)))
                log.error(traceback.format_exc())


    async def plot(self):
        """
        Long-running task that regularly plots the network and latencies amont its nodes.

        :returns: nothing; throws expection in case of error
        """
        i = 0
        while self.started:
            await asyncio.sleep(30)
            if self.connected and self.latency is not None:
                i += 1
                file_name = "net_viz-{:04d}".format(i)
                log.info("Creating visualization [ {} ]".format(file_name))
                try:
                    await asyncio.to_thread(network_viz, {self.peer_id: self.latency}, file_name)
                except Exception as e:
                    log.error("Could not create visualization [ {} ]: {}".format(file_name, str(e)))
                    log.error(traceback.format_exc())


    async def ping_peers(self):
        """
        Long-running task that pings the peers of this node.

        :returns: nothing; the recorded latency measures are kept in dictionary
                  self.latency {otherPeerId: [latency, latency, ...]}
        """
        ping_latency= "latency"

        while self.started:
            # check that we are still connected, avoiding full CPU usage
            await asyncio.sleep(1)
            if not self.connected:
                log.debug("ping_peers() waiting for connection")
                continue

            # randomly sample the peer set to converge towards
            # a uniform distribution of pings among peers
            sampled_peers = random.sample(sorted(self.peers),
                                          len(self.peers))
            for peer_id in sampled_peers:
                # create a list to keep the latency measures of new peers
                if peer_id not in self.latency.keys():
                    self.latency[peer_id] = list()

                try:
                    log.debug(f"Pinging peer {peer_id}")
                    response = await self.hoprd_api.ping(peer_id= peer_id)
                    json_body = response.json()

                    if ping_latency in json_body:
                        latency = int(json_body[ping_latency])
                        self.latency[peer_id].append(latency)

                        # keep the last 100 latency measures
                        if len(self.latency[peer_id]) > 100:
                            self.latency[peer_id].pop(0)
                        log.info(f"Got latency measure ({latency} ms) from peer {peer_id}")
                    else:
                        self.latency[peer_id].append(-1)
                        log.warning(f"No answer from peer {peer_id}")

                except Exception as exception:
                    log.error(f"Could not ping using {self.hoprd_api._api_url}: {exception}")
                    log.error(traceback.format_exc())

                finally:
                    # check that we are still connected
                    if not self.connected:
                        break
                    else:
                        # throttle the API requests towards the node
                        await asyncio.sleep(5)


    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info("Starting node")
        if len(self.tasks) == 0:
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
