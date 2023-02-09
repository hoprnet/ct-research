import asyncio
import json
import logging
import requests
import traceback


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

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dictionary to keep the last 100 latency measures {peer: [latency, latency, ...]}, see:
        self.latency = dict[str, list[int]]()

        # a set to keep track of the running tasks
        self.tasks = set()
        log.debug("Created HOPR node instance")


    def _req(self, end_point: str, method: str="GET", payload: dict=None) -> dict:
        """
        Connects to the 'end_point' of this node's REST API, using 'method' (either GET or POST).
        Optionally attaches 'payload' as JSON string to the request.

        :returns: a JSON dictionary; throws an exception if failed.
        """
        ret_value  = dict()
        target_url = "{}/api/v2{}".format(self.url, end_point)
        log.debug("Connecting to {}".format(target_url))

        try:
            if payload:
                data_payload = json.dumps(payload)
            else:
                data_payload = None

            # FIXME: using 'requests' blocks the event loop!
            response = requests.request(method,
                                        target_url,
                                        headers=self.headers,
                                        data=data_payload)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    ret_value = response.json()
                else:
                    log.error("Expected application/json, but got {}".format(content_type))
            else:
                log.error("{} request {} returned status code {}".format(method,
                                                                         self.url,
                                                                         response.status_code))
        except Exception as e:
            log.error("Could not {} from {}: exception ocurred".format(method,
                                                                       self.url))
            log.error(traceback.format_exc())
        finally:
            return ret_value


    def connect(self):
        """
        Connects to this HOPR node, returning its peer_id.
        """
        end_point = "/account/addresses"

        log.debug("Connecting to node")
        try:
            # gather the peerId
            json_body = self._req(end_point)
            if len(json_body) > 0:
                self.peer_id = json_body["hopr"]
                log.info("Connected HOPR node has peerId {}".format(self.peer_id))

        except Exception as e:
            log.error("Node could not connect to {}".format(end_point))
            log.error(traceback.format_exc())


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
        status    = "connected"
        end_point = "/node/peers"
        
        try:
            log.debug("Gathering connected peers")
            while self.connected:
                json_body = self._req(end_point)
                if status in json_body:
                    for p in json_body[status]:
                        peer = p["peerId"]
                        if peer not in self.peers:
                            self.peers.add(peer)
                            log.info("Found new peer {}".format(peer))
                # sleep for a while
                await asyncio.sleep(10)
            else:
                log.warning("Node not connected")

        except Exception as e:
            log.error("Could not get peers from {}".format(end_point))
            log.error(traceback.format_exc())


    async def ping_peers(self):
        """
        Long-running task that pings the peers of this node.

        :returns: nothing; the recorded latency measures are kept in dictionary 
                  self.latency {otherPeerId: [latency, latency, ...]}
        """
        end_point = "/node/ping"

        try:
            while self.connected:
                for p in self.peers:
                    # we mustr be connected before pinging
                    if not self.connected:
                        continue
                    await asyncio.sleep(5)

                    # create a list to keep the latency measures of new peers
                    if p not in self.latency.keys():
                        self.latency[p] = list()

                    log.info("Pinging peer {}".format(p))
                    json_body = self._req(end_point,
                                          method="POST",
                                          payload={'peerId': p})
                    if "latency" in json_body:
                        latency = int(json_body["latency"])
                        self.latency[p].append(latency)

                        # keep the last 100 latency measures
                        if len(self.latency[p]) > 100:
                            self.latency[p].pop(0)

                        log.info("Got latency measure ({} ms) from peer {}".format(latency,
                                                                                   p))
                    else:
                        self.latency[p].append(-1)
                        log.warning("No answer from peer {}".format(p))
            else:
                log.warning("Node not connected")

        except Exception as e:
            log.error("Could not get peers from {}: exception occurred".format(end_point))
            log.error(traceback.format_exc())


    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info("Starting node")
        self.connect()
        if len(self.tasks) == 0:
            self.tasks.add(asyncio.create_task(self.gather_peers()))
            self.tasks.add(asyncio.create_task(self.ping_peers()))
        await asyncio.gather(*self.tasks)


    def stop(self):
        """
        Stops the running tasks of this node
        """
        log.info("Stopping node {}".format(self.peer_id))
        self.disconnect()
        for t in self.tasks:
            t.add_done_callback(self.tasks.discard)
        asyncio.gather(*self.tasks)
