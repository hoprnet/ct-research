import asyncio
from typing import Optional

import aiohttp
from core.baseclass import Base

from .http_method import HTTPMethod
from .protocol import Protocol
from .request_objects import (
    ApiRequestObject,
    CreateSessionBody,
    DeleteSessionBody,
    FundChannelBody,
    GetChannelsBody,
    GetPeersBody,
    OpenChannelBody,
    SessionCapabilitiesBody,
    SessionPathBodyHops,
    SessionPathBodyRelayers,
    SessionTargetBody,
)
from .response_objects import (
    Addresses,
    Balances,
    Channels,
    ConnectedPeer,
    Infos,
    OpenedChannel,
    Session,
    TicketPrice,
    TicketProbability,
)

MESSAGE_TAG = 0x1245


class HoprdAPI(Base):
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self.host = url
        self.headers = {"Authorization": f"Bearer {token}"}
        self.prefix = "/api/v3/"

    @property
    def log_prefix(cls) -> str:
        return "api"

    async def __call(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: ApiRequestObject = None,
    ):
        try:
            headers = {"Content-Type": "application/json"}
            async with aiohttp.ClientSession(headers=self.headers) as s:
                async with getattr(s, method.value)(
                    url=f"{self.host}{self.prefix}{endpoint}",
                    json={} if data is None else data.as_dict,
                    headers=headers,
                ) as res:
                    try:
                        return res.status, await res.json()
                    except:
                        return res.status, await res.text()

        except OSError as e:
            self.error(f"OSError calling {method.value} {endpoint}: {e}")

        except Exception as e:
            self.error(f"Exception calling {method.value} {endpoint}. error is: {e}")

        return (False, None)

    async def __call_api(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: ApiRequestObject = None,
        timeout: int = 60,
    ) -> tuple[bool, Optional[object]]:
        try:
            return await asyncio.wait_for(
                asyncio.create_task(self.__call(method, endpoint, data)),
                timeout=timeout,
            )

        except asyncio.TimeoutError:
            self.error(f"TimeoutError calling {method} {endpoint}")
            return (False, None)

    async def balances(self) -> Optional[Balances]:
        """
        Returns the balance of the node.
        :return: balances: Balances | undefined
        """
        is_ok, response = await self.__call_api(HTTPMethod.GET, "account/balances")
        return Balances(response) if is_ok else None

    async def open_channel(
        self, peer_address: str, amount: str
    ) -> Optional[OpenedChannel]:
        """
        Opens a channel with the given peer_address and amount.
        :param: peer_address: str
        :param: amount: str
        :return: channel id: str | undefined
        """

        data = OpenChannelBody(amount, peer_address)

        is_ok, response = await self.__call_api(HTTPMethod.POST, "channels", data)
        return OpenedChannel(response) if is_ok else None

    async def fund_channel(self, channel_id: str, amount: float) -> bool:
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: float
        :return: bool
        """
        data = FundChannelBody(amount)

        is_ok, _ = await self.__call_api(
            HTTPMethod.POST, f"channels/{channel_id}/fund", data
        )
        return is_ok

    async def close_channel(self, channel_id: str) -> bool:
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        is_ok, _ = await self.__call_api(HTTPMethod.DELETE, f"channels/{channel_id}")
        return is_ok

    async def channels(self) -> Channels:
        """
        Returns all channels.
        :return: channels: list
        """
        params = GetChannelsBody("true", "false")

        is_ok, response = await self.__call_api(
            HTTPMethod.GET, f"channels?{params.as_header_string}"
        )
        return Channels(response) if is_ok else None

    async def peers(
        self,
        quality: float = 0.5,
    ) -> list[ConnectedPeer]:
        """
        Returns a list of peers.
        :param: param: list or str = "peerId"
        :param: status: str = "connected"
        :param: quality: int = 0..1
        :return: peers: list
        """
        params = GetPeersBody(quality)

        is_ok, response = await self.__call_api(
            HTTPMethod.GET, f"node/peers?{params.as_header_string}"
        )

        if not is_ok:
            return []

        if "connected" not in response:
            self.warning("No 'connected' field returned from the API")
            return []

        return [ConnectedPeer(peer) for peer in response["connected"]]

    async def get_address(self) -> Optional[Addresses]:
        """
        Returns the address of the node.
        :return: address: str | undefined
        """
        is_ok, response = await self.__call_api(HTTPMethod.GET, "account/addresses")

        return Addresses(response) if is_ok else None

    async def node_info(self) -> Optional[Infos]:
        """
        Gets informations about the HOPRd node.
        :return: Infos
        """
        is_ok, response = await self.__call_api(HTTPMethod.GET, "node/info")
        return Infos(response) if is_ok else None

    async def ticket_price(self) -> Optional[TicketPrice]:
        """
        Gets the ticket price set by the oracle.
        :return: TicketPrice
        """
        is_ok, response = await self.__call_api(HTTPMethod.GET, "network/price")
        return TicketPrice(response) if is_ok else None

    async def winning_probability(self) -> Optional[TicketProbability]:
        """
        Gets the winning probability set by the oracle.
        :return: TicketProbability
        """
        is_ok, response = await self.__call_api(HTTPMethod.GET, "network/probability")
        return TicketProbability(response) if is_ok else None

    async def get_sessions(self, protocol: Protocol = Protocol.TCP) -> list[Session]:
        """
        Lists existing Session listeners for the given IP protocol
        :param: protocol: Protocol
        :return: list[Session]
        """
        is_ok, response = await self.__call_api(
            HTTPMethod.GET, f"session/{protocol.value}"
        )
        return [Session(s) for s in response] if is_ok else None

    async def post_session(
        self,
        destination: str,
        listen_host: str,
        relayer: str,
        target: str,
        protocol: Protocol = Protocol.UDP,
        do_retransmission=False,
        do_segmentation=False,
    ) -> Session:
        """
        Creates a new client session returning the given session listening host & port over TCP or UDP.
        :param: destination: PeerID of the recipient
        :param: listen_host: str
        :param: relayer: PeerID of the relayer
        :param: target: Target (plain, not sealed)
        :param: protocol: Protocol (UDP or TCP)
        :param: do_retransmission: Enables packet retransmission
        :param: do_segmentation: Enables packet segmentation
        :return: Session
        """
        capabilities_body = SessionCapabilitiesBody(do_retransmission, do_segmentation)
        target_body = SessionTargetBody(plain=target)
        path_body = (
            SessionPathBodyRelayers(relayers=[relayer])
            if isinstance(relayer, str)
            else SessionPathBodyHops(hops=relayer)
        )
        data = CreateSessionBody(
            capabilities_body.as_array,
            destination,
            listen_host,
            path_body.as_dict,
            target_body.as_dict,
        )

        is_ok, response = await self.__call_api(
            HTTPMethod.POST, f"session/{protocol.value}", data
        )

        return Session(response) if is_ok else None

    async def close_session(
        self, ip: str, port: int, protocol: Protocol = Protocol.TCP
    ) -> bool:
        """
        Closes an existing Sessino listener for the given IP protocol, IP and port.
        :param: ip: str
        :param: port: int
        :param: protocol: Protocol
        """
        data = DeleteSessionBody(ip, port)

        is_ok, _ = await self.__call_api(
            HTTPMethod.DELETE, f"session/{protocol.value}", data
        )

        return is_ok

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 after max `timeout` seconds.
        """
        return await HoprdAPI.checkStatus(f"{self.host}/healthyz", 200, timeout)

    @classmethod
    async def checkStatus(cls, url: str, target: int, timeout: int = 20) -> bool:
        """
        Checks if the given URL is returning 200 after max `timeout` seconds.
        """

        async def _check_url(url: str):
            while True:
                try:
                    async with aiohttp.ClientSession() as s, s.get(url) as response:
                        return response
                except Exception:
                    await asyncio.sleep(0.25)

        try:
            response = await asyncio.wait_for(_check_url(url), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        else:
            return response.status == target
