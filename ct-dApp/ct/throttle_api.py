from hoprd import wrapper


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
    
    
    async def withdraw(self, currency, amount, address):
        return await self.wrapper.withdraw(currency, amount, address)
    
    async def balance(self):
        return await self.wrapper.balance()
    
    async def set_alias(self, peer_id, alias):
        return await self.wrapper.set_alias(peer_id, alias)
    
    async def get_alias(self, alias):
        return await self.wrapper.get_alias(alias)
    
    async def remove_alias(self, alias):
        return await self.wrapper.remove_alias(alias)
    
    async def get_settings(self):
        return await self.wrapper.get_settings()
    
    async def get_all_channels(self, include_closed: bool):
        return await self.wrapper.get_all_channels(include_closed)
    
    async def get_channel_topology(self, full_topology: bool):
        return await self.wrapper.get_channel_topology(full_topology)
    
    async def get_tickets_in_channel(self, include_closed: bool):
        return await self.wrapper.get_tickets_in_channel(include_closed)
    
    async def redeem_tickets_in_channel(self, peer_id):
        return await self.wrapper.redeem_tickets_in_channel(peer_id)
    
    async def redeem_tickets(self):
        return await self.wrapper.redeem_tickets()
    
    async def ping(self, peer_id):
        return await self.wrapper.ping(peer_id)
    
    async def peers(self, **kwargs):
        return await self.wrapper.peers(**kwargs)
    
    async def get_address(self):
        return await self.wrapper.get_address()
    
    async def send_message(self, destination, message, hops):
        return await self.wrapper.send_message(destination, message, hops)