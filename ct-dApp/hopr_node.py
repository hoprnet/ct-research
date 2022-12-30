import asyncio
import aiohttp
import logging

from aiohttp.client_exceptions import ClientConnectorError


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

        # client session is reusable, see:
        # - https://stackoverflow.com/questions/51908915/how-to-manage-a-single-aiohttp-clientsession
        # - https://github.com/aio-libs/aiohttp/blob/master/docs/faq.rst#why-is-creating-a-clientsession-outside-of-an-event-loop-dangerous
        self.session = None

        # a flag to indicate the pinging task is running, see:
        # - start_pinging(...)
        self.is_pinging = False

        # a list to keep the last 100 latency measures
        # - start_pinging(...)
        self.latency = list()
        log.debug("Created HOPR node instance")


    async def _create_session(self):
        """
        :returns: nothing; throws an exception if the session was not created.
        """
        if (self.session is not None) and (type(self.session) == aiohttp.ClientSession):
            log.warning("Tried to create a new session, but it already exists")
        else:
            self.session = aiohttp.ClientSession()
            log.info("Opened new session")


    async def _get(self, end_point: str, params: dict=None) -> dict:
        """
        Connects to the 'end_point' of this node's REST API.
        Optionally passes 'params' as key-value pairs, see
        https://docs.aiohttp.org/en/stable/client_quickstart.html#passing-parameters-in-urls

        :returns: a JSON dictionary; throws an exception if GET failed.
        """
        ret_value  = dict()
        target_url = "{}/api/v2{}".format(self.url, end_point)
        log.debug("Connecting to {}".format(target_url))

        try:
            async with self.session.get(target_url,
                                        headers=self.headers,
                                        params=params,
                                        ssl=False) as response:
                if response.status == 200:
                    if response.content_type == "application/json":
                        ret_value = await response.json()
                    else:
                        log.error("Expected application/json, but node returned {}".format(response.content_type))
                else:
                    log.error("Node {} returned status code {}".format(self.url,
                                                                       response.status))

        except ClientConnectorError as e:
            msg = "Cannot reach URL {}: {}".format(self.url,
                                                   str(e))
            log.error(msg)
        finally:
            return ret_value


    async def connect(self) -> bool:
        """
        Connects to this HOPR node, saving its peer_id.
        :returns: True if connection was successful; or throws an exception.
        """
        ret_value = False
        end_point = "/account/addresses"

        try:
            # create a new session if needed
            if not self.session:
                await self._create_session()

            # gather the peerId
            json_body = await self._get(end_point)
            if len(json_body) > 0:
                self.peer_id = json_body["hopr"]
                ret_value    = True
                log.debug("HOPR node has peerId {}".format(self.peer_id))
                log.debug("Self is {}".format(self))
            else:
                log.warning("Could get peerId")

        except Exception as e:
            log.warning("Could not connect: exception occurred {}".format(str(e)))
        finally:
            return ret_value


    async def disconnect(self):
        """
        :returns: nothing; throws an exception if the session was not closed.
        """
        if self.is_pinging:
            await self.stop_pinging()
        if self.session and (not self.session.closed):
            await self.session.close()
            log.info("Session closed")


    async def get_peers(self, status: str='connected') -> set:
        """
        :returns: a set of peerIds with 'status', where 'status' can be one of 'connected' or 'announced'.
        """
        STATUS    = ('connected', 'announced')
        ret_value = set()

        if (status is not None) and (status not in STATUS):
            log.error('Unknown status {}. Try {}'.format(status,
                                                         STATUS))
            return ret_value
        try:
            if not self.peer_id:
                if not await self.connect():
                    log.warning("Could not get peers")
                else:
                    end_point = "/node/peers"
                    log.debug("Trying to get node's <{}> peers".format(status))
                    json_body = await self._get(end_point)
                    log.debug("get_peers JSON received: {}".format(json_body))
                    for p in json_body[status]:
                        ret_value.add(p["peerId"])
            else:
                log.error("PeerId is None")
                log.debug("Self is {}".format(self))

        except Exception as e:
            log.warning("Could not get peers: exception occurred {}".format(str(e)))
        finally:
            return ret_value


    async def start_pinging(self, other_peer_id: str, interval: int=5):
        """
        Long-running task that pings 'other_peer_id' every 'interval' seconds.
        It saves the last 100 latency measures in 'self.latency'.
        :returns: nothing; the recorded latency measures are kept in 'self.latency'.
        """
        if self.is_pinging:
            log.warning("Tried to start pinging, but it's already running")
            return
        if not self.peer_id:
            await self.connect()

        log.info("Started pinging {}".format(other_peer_id))
        end_point       = "/node/ping"
        self.is_pinging = True
        while self.is_pinging:
            json_body = await self._get(end_point,
                                        params={'peerId': other_peer_id})
            latency   = int(json_body["latency"])
            self.latency.append(latency)
            log.debug("Saved latency measure ({} ms) from node {}".format(latency,
                                                                          other_peer_id))
            # keep the last 100 latency measures
            if len(self.latency) > 100:
                self.latency.pop(0)
            # wait
            await asyncio.sleep(interval)
        log.info("Stopped pinging {}".format(other_peer_id))


    async def stop_pinging(self):
        """
        Stops the long-running task that pings.
        :returns: nothing
        """
        if not self.is_pinging:
            log.warning("Tried to stop pinging, but it's not running")
        else:
            self.is_pinging = False
            log.info("Trying to stop pinging")
