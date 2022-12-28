import aiohttp
import logging

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
        log.debug("Created HOPR node instance")

    async def connect(self):
        target_url = "{}/api/v2/account/addresses".format(self.url)
        log.debug("Connecting to {}".format(target_url))

        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get(target_url, ssl=False) as response:
                if response.status == 200:
                    assert(response.content_type == "application/json")
                    json_body    = await response.json()
                    self.peer_id = json_body['hopr']
                    log.info("Node has peer ID {}".format(self.peer_id))
                else:
                    log.error("Node {} returned code {}".format(self.url,
                                                                response.status))
