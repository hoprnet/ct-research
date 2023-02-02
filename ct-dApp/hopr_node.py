import asyncio
import json
import logging
import aiohttp
import traceback


log = logging.getLogger(__name__)


class HoprNode():
    """
    Implements the functionality of a HOPR node through its REST API and WebSocket
    """
    def __init__(self, url, key):
        """
        :returns: a new instance of a HOPR node using 'url' and API 'key'
        """
        self.api_key = key
        self.headers = {'X-Auth-Token': self.api_key}
        self.url     = url
        self.peer_id = None

        # a set to keep the peers of this node, see:
        # - get_peers(...)
        self.peers = set()

        # a dictionary to keep the last 100 latency measures {peer: [latency, latency, ...]}, see:
        # - start_pinging(...)
        # - stop_pinging(...)
        self.latency = dict()
        log.debug("Created HOPR node instance")


    async def _req(self, end_point: str, method: str="GET", params: dict=None) -> dict:
        """
        Connects to the 'end_point' of this node's REST API, using 'method' (either GET or POST).
        Optionally passes 'params' as key-value pairs.
        :returns: a JSON dictionary; throws an exception if failed.
        """
        ret_value = dict()
        target_url = f"{self.url}/api/v2{end_point}"
        log.debug(f"Connecting to {target_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, target_url, headers=self.headers, params=params) as response:
                    if response.status == 200:
                        content_type = response.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            ret_value = await response.json()
                        else:
                            log.error(f"Expected application/json, but node returned {content_type}")
                    else:
                        log.error(f"{method} request {self.url} returned status code {response.status}")
        except Exception as e:
            log.error(f"Could not {method} from {self.url}: exception occurred")
            log.error(e)
        finally:
            return ret_value


    async def connect(self) -> str:
        """
        Connects to this HOPR node, returning its peer_id.
        :returns: this node's peerId if connection was successful (or None).
        """
        ret_value = None
        end_point = "/account/addresses"

        log.debug("Connecting to node")
        try:
            # gather the peerId
            json_body = await self._req(end_point)
            if len(json_body) > 0:
                self.peer_id = json_body["hopr"]
                ret_value    = self.peer_id
                log.info("Connected HOPR node has peerId {}".format(self.peer_id))

        except Exception as e:
            log.error("Node could not connect to {}: exception occurred.".format(end_point))
            log.error(traceback.format_exc())
            log.error(e)
        finally:
            return ret_value


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
        log.info("Disconnected HOPR node")


    async def gather_peers(self):
        """
        Long-running task that continously updates the set of peers connected to this node.

        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """
        status    = "connected"
        end_point = "/node/peers"
        
        try:
            log.info("Gathering connected peers")
            while True:
                if self.connected:
                    json_body = await self._req(end_point)
                    if status in json_body:
                        for p in json_body[status]:
                            peer = p["peerId"]
                            if peer not in self.peers:
                                self.peers.add(peer)
                                log.info("Found connected peer {}".format(peer))
                else:
                    log.error("Node not connected")
                # sleep for a while
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            log.info("Stopped gathering...")

        except Exception as e:
            log.error("Could not get peers from {}: exception occurred".format(end_point))
            log.error(traceback.format_exc())
            log.error(e)


    async def ping_peer(self, other_peer_id: str):
        """
        Long-running task that pings 'other_peer_id'.

        :returns: nothing; the recorded latency measures are kept in dictionary 
                  self.latency {otherPeerId: [latency, latency, ...]}
        """
        end_point = "/node/ping/"

        try:
            log.info("Pinging peer {}".format(other_peer_id))
            while True:
                if self.connected:
                    json_body = self._req(end_point,
                                          method="POST",
                                          params={'peerId': other_peer_id}) 
                    if "latency" in json_body:
                        latency   = int(json_body["latency"])
                        if other_peer_id not in self.latency.keys():
                            self.latency[other_peer_id] = list()
                        self.latency[other_peer_id].append(latency)

                        # keep the last 100 latency measures
                        if len(self.latency[other_peer_id]) > 100:
                            self.latency[other_peer_id].pop(0)

                        log.info("Got latency measure ({} ms) from peer {}".format(latency,
                                                                                   other_peer_id))
                    else:
                        log.warning("No answer from peer {}".format(other_peer_id))
                else:
                    log.error("Node not connected")
                # sleep for a while
                await asyncio.sleep(2)
        
        except asyncio.CancelledError:
            log.info("Stopped pinging peer {}".format(other_peer_id))

        except Exception as e:
            log.error("Could not get peers from {}: exception occurred".format(end_point))
            log.error(traceback.format_exc())
            log.error(e)
