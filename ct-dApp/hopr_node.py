import asyncio
import logging
import requests
import traceback
import random

from http_req import Http_req
from viz import network_viz


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
        self.headers = {'X-Auth-Token': self.api_key,
                        'Content-Type': 'application/json'}
        self.url     = url
        self.peer_id = None
        
        # Class that implements the functionallity of http requests
        self.http_req = Http_req()

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dictionary to keep the last 100 latency measures {peer: [latency, latency, ...]}
        self.latency = dict[str, list[int]]()

        # a set to keep track of the running tasks
        self.tasks = set()
        self.started = False
        log.debug("Created HOPR node instance")


    def _get_url(self, end_point: str) -> str:
        """
        :returns: a valid HOPRd API endpoint.
        """
        return "{}/api/v2{}".format(self.url, end_point)


    async def _req(self, target_url: str, method: str="GET", payload: dict[str, str]=None) -> dict[str, str]:
        """
        Connects to 'target_url' of this node's REST API, using 'method' (either GET or POST).
        Optionally attaches 'payload' as JSON string to the request.

        :returns: a JSON dictionary; throws an exception if failed.
        """
        response = await self.http_req.send_async_req(method, target_url, self.headers, payload)

        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.json()
            else:
                log.error("Expected application/json, but got {}".format(content_type))
                return {'response': response.text}
        else:
            log.error("{} {} returned status code {}".format(method,
                                                             target_url,
                                                             response.status_code))
            return {'': ''}


    async def connect(self):
        """
        Connects to this HOPR node, returning its peer_id.
        """
        url = self._get_url("/account/addresses")

        log.debug("Connecting to node")
        while self.started:
            try:
                # gather the peerId
                json_body = await self._req(url)
                if "hopr" in json_body:
                    self.peer_id = json_body["hopr"]
                    log.info("HOPR node {} is up".format(self.peer_id))
                else:
                    self.peer_id = None
                    log.info("HOPR node is down")

            except requests.exceptions.ConnectionError:
                self.peer_id = None
                log.info("HOPR node is down")
                
            except Exception as e:
                self.peer_id = None
                log.error("Could not connect to {}: {}".format(url, str(e)))
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
        status = "connected"
        url    = self._get_url("/node/peers")
        
        while self.started:
            # check that we are still connected
            if not self.connected:
                log.debug("gather_peers() waiting for connection")
                await asyncio.sleep(1)
                continue

            try:
                json_body = await self._req(url)
                if status in json_body:
                    for p in json_body[status]:
                        peer = p["peerId"]
                        if peer not in self.peers:
                            self.peers.add(peer)
                            log.info("Found new peer {}".format(peer))
                await asyncio.sleep(5)

            except requests.exceptions.ReadTimeout:
                log.warning("No answer from peer {}".format(self.peer_id))

            except Exception as e:
                log.error("Could not get peers from {}: {}".format(url, str(e)))
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
        url = self._get_url("/node/ping")

        while self.started:
            # check that we are still connected
            await asyncio.sleep(1)
            if not self.connected:
                log.debug("ping_peers() waiting for connection")
                continue

            # randomly sample the peer set to converge towards
            # a uniform distribution of pings among peers
            sampled_peers = random.sample(sorted(self.peers),
                                          len(self.peers))
            for p in sampled_peers:
                # create a list to keep the latency measures of new peers
                if p not in self.latency.keys():
                    self.latency[p] = list()

                try:
                    log.debug("Pinging peer {}".format(p))
                    json_body = await self._req(url,
                                                method="POST",
                                                payload={'peerId': p})
                    if "latency" in json_body:
                        latency = int(json_body["latency"])
                        self.latency[p].append(latency)

                        # keep the last 100 latency measures
                        if len(self.latency[p]) > 100:
                            self.latency[p].pop(0)

                        log.info(f"Got latency measure ({latency} ms) from peer {p}")
                    else:
                        self.latency[p].append(-1)
                        log.warning(f"No answer from peer {p}")

                except requests.exceptions.ReadTimeout:
                    log.warning(f"No answer from peer {p}")

                except Exception as e:
                    log.error(f"Could not ping using {url}: {e}")
                    log.error(traceback.format_exc())

                finally:
                    # check that we are still connected
                    if not self.connected:
                        break
                    else:
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
