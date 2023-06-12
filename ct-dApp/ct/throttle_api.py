from hoprd import wrapper
import httpx

class ThrottledHoprdAPI:
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
    
    async def _safe_call(self, func, *args, **kwargs):
        try:
            response = await func(*args, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                raise ValueError(e.response.json()['error'])
            else:
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

        return await self._safe_call(method, *args)
    
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
    
    async def ping(self, peer_id):
        method = self.wrapper.ping
        args = [peer_id]

        return await self._safe_call(method, *args)
    
    async def peers(self, **kwargs):
        method = self.wrapper.peers

        return await self._safe_call(method, **kwargs)
    
    async def get_address(self):
        method = self.wrapper.get_address

        return await self._safe_call(method)
    
    async def send_message(self, destination, message, hops):
        method = self.wrapper.send_message
        args = [destination, message, hops]
        
        return await self._safe_call(method, *args)