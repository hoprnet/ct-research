import traceback
from hoprd import wrapper
from typing import Callable

import logging

log = logging.getLogger(__name__)

class HoprdAPIHelper:
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
    
    async def _safe_call(self, func: Callable, *args, **kwargs):
        try:
            response = await func(*args, **kwargs)
            response.raise_for_status()
        except Exception as e:
            raise e
        else:
            return response
            
    async def withdraw(self, currency, amount, address):
        method = self.wrapper.withdraw
        args = [currency, amount, address]

        return await self._safe_call(method, *args)
    
    async def balance(self):
         method = self.wrapper.balance

         return await self._safe_call(method)
    
    async def set_alias(self, peer_id, alias):
        method = self.wrapper.set_alias
        args = [peer_id, alias]

        return await self._safe_call(method, *args)
    
    async def get_alias(self, alias):
        method = self.wrapper.get_alias
        args = [alias]

        return await self._safe_call(method, *args)
    
    async def remove_alias(self, alias):
        method = self.wrapper.remove_alias
        args = [alias]

        return await self._safe_call(method, *args).json()
    
    async def get_settings(self):
        method = self.wrapper.get_settings

        return await self._safe_call(method)
    
    async def get_all_channels(self, include_closed: bool):
        method = self.wrapper.get_all_channels
        args = [include_closed]

        return await self._safe_call(method, *args)
    
    async def get_channel_topology(self, full_topology: bool):
        method = self.wrapper.get_channel_topology
        args = [full_topology]

        return await self._safe_call(method, *args)
    
    async def get_tickets_in_channel(self, include_closed: bool):
        method = self.wrapper.get_tickets_in_channel
        args = [include_closed]

        return await self._safe_call(method, *args)
    
    async def redeem_tickets_in_channel(self, peer_id):
        method = self.wrapper.redeem_tickets_in_channel
        args = [peer_id]

        return await self._safe_call(method, *args)
    
    async def redeem_tickets(self):
        method = self.wrapper.redeem_tickets
        return await self._safe_call(method)
    
    async def ping(self, peer_id, metric="latency"):
        method = self.wrapper.ping
        args = [peer_id]

        try:
            log.debug(f"Pinging peer {peer_id}")
            response = await self._safe_call(method, *args)
        except Exception as e:
            log.error(f"Error pinging peer {peer_id}: {e}")
            log.error(traceback.format_exc())
            return None
        else:
            json_body = response.json()

            if json_body is None:
                log.error(f"Peer {peer_id} not reachable using {self.api.url}")
                return None
            
            if metric not in json_body:
                log.error(f"No {metric} measure from peer {peer_id}")
                return None
            
            log.info(f"Measured {json_body[metric]}({metric}) from peer {peer_id}")
            return json_body[metric]
   
    async def peers(self, param: str="peerId", **kwargs):
        method = self.wrapper.peers
        status = "connected"

        try:
            log.debug("Getting peers")
            response = await self._safe_call(method, **kwargs)
        except Exception as e:
            log.error(f"Could not get peers from {self.api.url}: {e}")
            log.error(traceback.format_exc())
            raise e
        else:
            json_body = response.json()

            if status not in json_body:
                log.error(f"No {status} from {self.api.url}")
                return None
            
            return [peer[param] for peer in json_body[status]]
 
    
    async def get_address(self, address: str):
        method = self.wrapper.get_address

        try:
            log.debug("Getting address")
            response = await self._safe_call(method)
        except Exception as e:
            raise e
        else:
            json_body = response.json()

            if address not in json_body:
                log.error(f"No {address} from {self.api.url}")
                return None
            
            return json_body.get(address, None)
    
    async def send_message(self, destination, message, hops):
        method = self.wrapper.send_message
        args = [destination, message, hops]
        
        return await self._safe_call(method, *args)