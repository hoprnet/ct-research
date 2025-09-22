import logging
from typing import Optional, Union

from api_lib import ApiLib

from ..components.balance import Balance
from . import request_objects as req
from . import response_objects as resp
from .http_method import HTTPMethod

logging.getLogger("api-lib").setLevel(logging.WARNING)


class HoprdAPI(ApiLib):
    """
    HOPRd API helper to handle exceptions and logging.
    """

    async def balances(self) -> Optional[resp.Balances]:
        """
        Returns the balance of the node.
        :return: balances: Balances | undefined
        """
        return await self.try_req(HTTPMethod.GET, "/account/balances", resp.Balances)

    async def open_channel(
        self, peer_address: str, amount: Balance
    ) -> Optional[resp.OpenedChannel]:
        """
        Opens a channel with the given peer_address and amount.
        :param: peer_address: str
        :param: amount: Balance
        :return: channel id: str | undefined
        """
        data = req.OpenChannelBody(amount.as_str, peer_address)
        return await self.try_req(HTTPMethod.POST, "/channels", resp.OpenedChannel, data)

    async def fund_channel(self, channel_id: str, amount: Balance) -> bool:
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: Balance
        :return: bool
        """
        data = req.FundChannelBody(amount.as_str)
        return await self.try_req(
            HTTPMethod.POST, f"/channels/{channel_id}/fund", data=data, return_state=True
        )

    async def close_channel(self, channel_id: str) -> bool:
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        return await self.try_req(HTTPMethod.DELETE, f"/channels/{channel_id}", return_state=True)

    async def channels(self, full_topology: bool = True) -> Optional[resp.Channels]:
        """
        Returns all channels.
        :return: channels: list
        """
        header = req.GetChannelsBody(full_topology, False)
        return await self.try_req(
            HTTPMethod.GET, f"/channels?{header.as_header_string}", resp.Channels
        )

    async def metrics(self) -> Optional[resp.Metrics]:
        """
        Returns the metrics of the node.
        :return: metrics: list
        """
        return await self.try_req(HTTPMethod.GET, "/metrics", resp.Metrics, use_api_prefix=False)

    async def peers(
        self,
        quality: float = 0.5,
        status: str = "connected",
    ) -> list[resp.ConnectedPeer]:
        """
        Returns a list of peers.
        :param: quality: int = 0..1
        :param: status: str = "connected"
        :return: peers: list
        """
        params = req.GetPeersBody(quality)

        if r := await self.try_req(HTTPMethod.GET, f"/node/peers?{params.as_header_string}"):
            return [resp.ConnectedPeer(peer) for peer in r.get(status, [])]
        else:
            return []

    async def address(self) -> Optional[resp.Addresses]:
        """
        Returns the address of the node.
        :return: address: Addresses | undefined
        """
        return await self.try_req(HTTPMethod.GET, "/account/addresses", resp.Addresses)

    async def node_info(self) -> Optional[resp.Infos]:
        """
        Gets informations about the HOPRd node.
        :return: Infos
        """
        return await self.try_req(HTTPMethod.GET, "/node/info", resp.Infos)

    async def ticket_price(self) -> Optional[resp.TicketPrice]:
        """
        Gets the ticket price set in the configuration file.
        :return: TicketPrice
        """

        if config := await self.try_req(HTTPMethod.GET, "/node/configuration", resp.Configuration):
            price = resp.TicketPrice(config.as_dict)
        else:
            price = None

        if price and price.value not in ["None", None]:
            return price

        return await self.try_req(HTTPMethod.GET, "/network/price", resp.TicketPrice)

    async def list_udp_sessions(self) -> list[resp.Session]:
        """
        Lists existing Session listeners over UDP
        :return: list[Session]
        """
        return await self.try_req(HTTPMethod.GET, "/session/udp", list[resp.Session])

    async def post_udp_session(
        self,
        destination: str,
        relayer: str,
        listen_host: str = ":0",
    ) -> Union[resp.Session, resp.SessionFailure]:
        """
        Creates a new session returning the session listening host & port over UDP.
        :param: destination: Address of the recipient
        :param: relayer: Address of the relayer
        :param: listen_host: str
        :return: Session
        """
        capabilities_body = req.SessionCapabilitiesBody()
        target_body = req.SessionTargetBody()
        path_body = req.SessionPathBodyRelayers([relayer])

        data = req.CreateSessionBody(
            capabilities_body.as_array,
            destination,
            listen_host,
            path_body.as_dict,
            path_body.as_dict,
            "0 KB",
            target_body.as_dict,
        )
        if r := await self.try_req(
            HTTPMethod.POST,
            "/session/udp",
            resp.Session,
            data=data,
            timeout=2,
        ):
            return r
        else:
            return resp.SessionFailure(
                {"error": "api call or timeout error", "status": "NO_SESSION_OPENED"}
            )

    async def close_session(self, session: resp.Session) -> bool:
        """
        Closes an existing Session listener for the given IP protocol, IP and port.
        :param: session: Session
        """
        return await self.try_req(HTTPMethod.DELETE, session.as_path, return_state=True, timeout=1)

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 before timeout.
        """
        return await self.timeout_check_success("/healthyz", timeout=timeout)
