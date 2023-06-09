from hoprd import wrapper


class ThrottledHoprdAPI:
    def __init__(self, url: str, token: str):
        self.api = wrapper.HoprdAPI(api_url=url, api_token=token)

        self._api_url = url
        self._api_token = token
    
    async def withdraw(self, currency, amount, address):
        return await self.api.withdraw(currency, amount, address)
    
    async def balance(self):
        return await self.api.balance()
    
    async def set_alias(self, peer_id, alias):
        return await self.api.set_alias(peer_id, alias)
    
    async def get_alias(self, alias):
        return await self.api.get_alias(alias)
    
    async def remove_alias(self, alias):
        return await self.api.remove_alias(alias)
    
    async def get_settings(self):
        return await self.api.get_settings()
    
    async def get_all_channels(self, include_closed: bool):
        return await self.api.get_all_channels(include_closed)
    
    async def get_channel_topology(self, full_topology: bool):
        return await self.api.get_channel_topology(full_topology)
    
    async def get_tickets_in_channel(self, include_closed: bool):
        return await self.api.get_tickets_in_channel(include_closed)
    
    async def redeem_tickets_in_channel(self, peer_id):
        return await self.api.redeem_tickets_in_channel(peer_id)
    
    async def redeem_tickets(self):
        return await self.api.redeem_tickets()
    
    async def ping(self, peer_id):
        return await self.api.ping(peer_id)
    
    async def peers(self, **kwargs):
        return await self.api.peers(**kwargs)
    
    async def get_address(self):
        return await self.api.get_address()
    
    async def send_message(self, destination, message, hops):
        return await self.api.send_message(destination, message, hops)