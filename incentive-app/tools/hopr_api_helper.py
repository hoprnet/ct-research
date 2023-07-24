import logging
from typing import Callable

import httpx
from hoprd import wrapper

log = logging.getLogger(__name__)


class HoprdAPIHelper:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self.wrapper = wrapper.HoprdAPI(api_url=url, api_token=token)

        self._url = url
        self._token = token

    @property
    def url(self) -> str:
        return self._url

    @property
    def token(self) -> str:
        return self._token

    async def _unsafe_call(self, func: Callable, *args, **kwargs):
        """
        Wrapper around each API call to handle exceptions
        """
        try:
            response = await func(*args, **kwargs)
            response.raise_for_status()
        except httpx.HTTPError:
            log.warning(f"Error calling `{func.__name__}`")

        return response

    async def _safe_call(self, func: Callable, *args, **kwargs):
        """
        Wrapper around each API call to handle exceptions
        """
        try:
            response = await func(*args, **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as e:
            log.exception(f"Error calling `{func.__name__}`")
            raise e
        else:
            return response

    async def withdraw(self, currency, amount, address):
        method = self.wrapper.withdraw
        args = [currency, amount, address]

        log.debug("Withdrawing")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error withdrawing")
            return None
        else:
            return response.json()

    async def balance(self):
        method = self.wrapper.balance

        log.debug("Getting balance")

        try:
            response = await self._safe_call(method)
        except httpx.HTTPError:
            log.exception
            return None
        else:
            return response.json()

    async def set_alias(self, peer_id, alias):
        method = self.wrapper.set_alias
        args = [peer_id, alias]

        log.debug("Setting alias")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error setting alias")
            return None
        else:
            return response.json()

    async def get_alias(self, alias):
        method = self.wrapper.get_alias
        args = [alias]

        log.debug("Getting alias")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error getting alias")
            return None
        else:
            return response.json()

    async def remove_alias(self, alias):
        method = self.wrapper.remove_alias
        args = [alias]

        log.debug("Removing alias")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error removing alias")
            return None
        else:
            return response.json()

    async def get_settings(self):
        method = self.wrapper.get_settings

        log.debug("Getting settings")

        try:
            response = await self._safe_call(method)
        except httpx.HTTPError:
            log.exception("Error getting settings")
            return None
        else:
            return response.json()

    async def open_channel(self, peer_id, amount):
        method = self.wrapper.open_channel
        args = [peer_id, amount]

        log.debug("Opening channel")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPStatusError:
            log.error("Error opening channel")
            return None
        except httpx.HTTPError:
            log.exception("Error opening channel")
            return None
        else:
            log.info(f"Channel opened with {peer_id}")
            return response.json()

    async def open_channel_safe(self, peer_id, amount):
        out_channels = await self.get_all_channels(False, "outgoing")

        connected_peers = [
            channel["peerId"] for channel in out_channels if channel["status"] == "Open"
        ]

        if peer_id in connected_peers:
            log.info(f"Channel with {peer_id} already opened")
            return None

        return await self.open_channel(peer_id, amount)

    async def close_channel(self, peer_id, direction):
        method = self.wrapper.close_channel

        args = [peer_id, direction]

        log.debug("Closing channel")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error closing channel")
            return None
        else:
            return response.json()

    async def get_all_channels(
        self, include_closed: bool, direction: str = None, key: str = None
    ):
        method = self.wrapper.get_all_channels
        args = [include_closed]

        log.debug("Getting all channels")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error getting all channels")
            return None
        else:
            data = response.json()

            if not direction and key:
                log.error("Cannot filter by key without direction")
                return data

            if direction and not key:
                data = data[direction]

            if direction and key:
                data = [channel[key] for channel in data[direction]]

            return data

    async def get_unique_safe_peerId_links(self):
        """
        Returns a dict containing all unique source_peerId-source_address links.
        """
        method = self.wrapper.get_channel_topology
        args = [True]  # full_topology=True ro retrieve the full topology

        log.debug("Getting channel topology")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error getting channel topology")
            return None
        else:
            unique_peerId_address = {}
            all_items = response.json()[
                "all"
            ]  # All to retrieve all channels (incomming and outgoing)

            for item in all_items:
                try:
                    source_peer_id = item["sourcePeerId"]
                    source_address = item["sourceAddress"]
                except KeyError:
                    log.exception("Error getting sourcePeerId or sourceAddress")
                    return None

                if source_peer_id not in unique_peerId_address:
                    unique_peerId_address[source_peer_id] = source_address

            return unique_peerId_address

    async def get_tickets_in_channel(self, include_closed: bool):
        method = self.wrapper.get_tickets_in_channel
        args = [include_closed]

        log.debug("Getting tickets in channel")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error getting tickets in channel")
            return None
        else:
            return response.json()

    async def redeem_tickets_in_channel(self, peer_id):
        method = self.wrapper.redeem_tickets_in_channel
        args = [peer_id]

        log.debug(f"Redeeming tickets in channel with peer {peer_id}")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception(f"Error redeeming tickets in channel with peer {peer_id}")
            return None
        else:
            return response.json()

    async def redeem_tickets(self):
        method = self.wrapper.redeem_tickets

        log.debug("Redeeming tickets")

        try:
            response = await self._safe_call(method)
        except httpx.HTTPError:
            log.exception("Error redeeming tickets")
            return None
        else:
            if response.status_code == 204:
                return None
            return response.json()

    async def ping(self, peer_id, metric="latency"):
        method = self.wrapper.ping
        args = [peer_id]

        log.debug(f"Pinging peer {peer_id[-5:]}")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception(f"Error pinging peer {peer_id}")
            return None
        else:
            json_body = response.json()

            if json_body is None:
                log.error(f"Peer {peer_id} not reachable using {self.url}")
                return None

            if metric not in json_body:
                log.error(f"No {metric} measure from peer {peer_id[-5:]}")
                return None

            log.info(f"Measured {json_body[metric]:3d}({metric}) from peer {peer_id}")
            return json_body[metric]

    async def peers(self, param: str = "peerId", status: str = "connected", **kwargs):
        method = self.wrapper.peers

        log.debug("Getting peers")

        try:
            response = await self._safe_call(method, **kwargs)
        except httpx.HTTPError:
            log.exception(f"Could not get peers from {self.url}")
            return None
        else:
            json_body = response.json()

            if status not in json_body:
                log.error(f"No {status} from {self.url}")
                return None

            if param not in json_body[status][0]:
                log.error(f"No {param} from {self.url}")
                return None

            return [peer[param] for peer in json_body[status]]

    async def get_address(self, address: str):
        method = self.wrapper.get_address

        log.debug("Getting address")

        try:
            response = await self._safe_call(method)
        except httpx.HTTPError:
            log.exception(f"Could not connect to {self.url}")
            return None
        else:
            json_body = response.json()

            if address not in json_body:
                log.error(f"No {address} from {self.url}")
                return None

            return json_body.get(address, None)

    async def send_message(self, destination, message, hops):
        method = self.wrapper.send_message
        args = [destination, message, hops]

        log.debug("Sending message")

        try:
            response = await self._safe_call(method, *args)
        except httpx.HTTPError:
            log.exception("Error sending message")
            return None
        else:
            return response.json()
