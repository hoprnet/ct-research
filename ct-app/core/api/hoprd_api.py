import asyncio
import json
import logging
from typing import Optional, Union

import aiohttp

from core.components.logs import configure_logging

from . import request_objects as request
from . import response_objects as response
from .http_method import HTTPMethod
from .protocol import Protocol

MESSAGE_TAG = 0x1245

configure_logging()
logger = logging.getLogger(__name__)


class HoprdAPI:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self.host = url
        self.headers = {"Authorization": f"Bearer {token}"}
        self.prefix = "/api/v3/"

    async def __call(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: request.ApiRequestObject = None,
    ):
        if endpoint != "messages":
            logger.debug(
                "Hitting API",
                {
                    "host": self.host,
                    "method": method.value,
                    "endpoint": endpoint,
                    "data": getattr(data, "as_dict", {}),
                },
            )
        try:
            headers = {"Content-Type": "application/json"}
            async with aiohttp.ClientSession(headers=self.headers) as s:
                async with getattr(s, method.value)(
                    url=f"{self.host}{self.prefix}{endpoint}",
                    json={} if data is None else data.as_dict,
                    headers=headers,
                ) as res:
                    try:
                        data = await res.json()
                    except Exception:
                        data = await res.text()

                    return (res.status // 200) == 1, data
        except OSError as err:
            logger.error(
                "OSError while doing an API call",
                {
                    "error": str(err),
                    "host": self.host,
                    "method": method.value,
                    "endpoint": endpoint,
                },
            )

        except Exception as err:
            logger.error(
                "Exception while doing an API call",
                {
                    "error": str(err),
                    "host": self.host,
                    "method": method.value,
                    "endpoint": endpoint,
                },
            )

        return (False, None)

    async def __call_api(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: request.ApiRequestObject = None,
        timeout: int = 60,
    ) -> tuple[bool, Optional[object]]:
        backoff = 0.5
        while True:
            try:
                result = await asyncio.wait_for(
                    asyncio.create_task(self.__call(method, endpoint, data)),
                    timeout=timeout,
                )
            except aiohttp.ClientConnectionError as err:
                backoff *= 2
                logger.exception(
                    "ClientConnection exception while doing an API call.",
                    {
                        "error": str(err),
                        "host": self.host,
                        "method": method.value,
                        "endpoint": endpoint,
                        "backoff": backoff,
                    },
                )
                if backoff > 10:
                    return (False, None)
                await asyncio.sleep(backoff)

            except asyncio.TimeoutError as err:
                logger.error(
                    "Timeout error while doing an API call",
                    {
                        "error": str(err),
                        "host": self.host,
                        "method": method.value,
                        "endpoint": endpoint,
                    },
                )
                return (False, None)
            else:
                return result

    async def balances(self) -> Optional[response.Balances]:
        """
        Returns the balance of the node.
        :return: balances: Balances | undefined
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "account/balances")
        return response.Balances(resp) if is_ok else None

    async def open_channel(
        self, peer_address: str, amount: str
    ) -> Optional[response.OpenedChannel]:
        """
        Opens a payment channel with a specified peer and amount.
        
        Args:
            peer_address: The address of the peer to open the channel with.
            amount: The amount to fund the channel.
        
        Returns:
            An OpenedChannel response object if successful, otherwise None.
        """
        data = request.OpenChannelBody(amount, peer_address)

        is_ok, resp = await self.__call_api(HTTPMethod.POST, "channels", data, timeout=90)
        return response.OpenedChannel(resp) if is_ok else None

    async def fund_channel(self, channel_id: str, amount: float) -> bool:
        """
        Funds an existing payment channel with the specified amount.
        
        Args:
            channel_id: The identifier of the channel to fund.
            amount: The amount to add to the channel.
        
        Returns:
            True if the channel was successfully funded, False otherwise.
        """
        data = request.FundChannelBody(amount)

        is_ok, _ = await self.__call_api(
            HTTPMethod.POST, f"channels/{channel_id}/fund", data, timeout=90
        )
        return is_ok

    async def close_channel(self, channel_id: str) -> bool:
        """
        Closes a payment channel by its ID.
        
        Args:
            channel_id: The identifier of the channel to close.
        
        Returns:
            True if the channel was closed successfully, False otherwise.
        """
        is_ok, _ = await self.__call_api(HTTPMethod.DELETE, f"channels/{channel_id}", timeout=90)
        return is_ok

    async def channels(self) -> response.Channels:
        """
        Retrieves all payment channels for the node.
        
        Returns:
            A Channels response object if successful; otherwise, None.
        """
        params = request.GetChannelsBody("true", "false")

        is_ok, resp = await self.__call_api(HTTPMethod.GET, f"channels?{params.as_header_string}")
        return response.Channels(resp) if is_ok else None

    async def peers(
        self,
        quality: float = 0.5,
    ) -> list[response.ConnectedPeer]:
        """
        Retrieves a list of connected peers filtered by a quality threshold.
        
        Args:
            quality: Minimum quality score (between 0 and 1) to filter peers.
        
        Returns:
            A list of ConnectedPeer objects representing peers with a quality above the specified threshold.
        """
        params = request.GetPeersBody(quality)

        is_ok, resp = await self.__call_api(HTTPMethod.GET, f"node/peers?{params.as_header_string}")

        if not is_ok:
            return []

        if "connected" not in resp:
            return []

        return [response.ConnectedPeer(peer) for peer in resp["connected"]]

    async def get_address(self) -> Optional[response.Addresses]:
        """
        Returns the address of the node.
        :return: address: str | undefined
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "account/addresses")
        return response.Addresses(resp) if is_ok else None

    async def node_info(self) -> Optional[response.Infos]:
        """
        Gets informations about the HOPRd node.
        :return: Infos
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "node/info")
        return response.Infos(resp) if is_ok else None

    async def ticket_price(self) -> Optional[response.TicketPrice]:
        """
        Retrieves the ticket price from the node's configuration.
        
        Returns:
            A TicketPrice object if the request is successful; otherwise, None.
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "node/configuration")
        return (
            response.TicketPrice(response.Configuration(json.loads(resp)).as_dict)
            if is_ok
            else None
        )

    async def get_sessions(self, protocol: Protocol = Protocol.UDP) -> list[response.Session]:
        """
        Retrieves all active session listeners for the specified protocol.
        
        Args:
            protocol: The IP protocol to filter sessions by (default is UDP).
        
        Returns:
            A list of Session objects representing the current session listeners for the given protocol. Returns an empty list if the request fails.
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, f"session/{protocol.name.lower()}")

        return [response.Session(s) for s in resp] if is_ok else []

    async def post_session(
        self,
        destination: str,
        relayer: str,
        listen_host: str = ":0",
        protocol: Protocol = Protocol.UDP,
    ) -> Union[response.Session, response.SessionFailure]:
        """
        Creates a new session with the specified destination, relayer, listening host, and protocol.
        
        Args:
            destination: PeerID of the session recipient.
            relayer: PeerID of the relayer node.
            listen_host: Host and port to listen on (default is ":0").
            protocol: Protocol to use for the session (UDP or TCP).
        
        Returns:
            A Session object if creation succeeds, or a SessionFailure object on failure.
        """
        capabilities_body = request.SessionCapabilitiesBody(
            protocol.retransmit, protocol.segment, protocol.no_delay
        )
        target_body = request.SessionTargetBody()
        path_body = request.SessionPathBodyRelayers([relayer])

        data = request.CreateSessionBody(
            capabilities_body.as_array,
            destination,
            listen_host,
            path_body.as_dict,
            target_body.as_dict,
        )

        is_ok, resp = await self.__call_api(
            HTTPMethod.POST, f"session/{protocol.name.lower()}", data
        )
        if resp is None:
            resp = {"error": "client error", "status": "CLIENT_ERROR"}
        return response.Session(resp) if is_ok else response.SessionFailure(resp)

    async def close_session(self, session: response.Session) -> bool:
        """
        Closes an existing Sessino listener for the given IP protocol, IP and port.
        :param: session: Session
        """
        is_ok, _ = await self.__call_api(
            HTTPMethod.DELETE, f"session/{session.protocol}/{session.ip}/{session.port}"
        )

        return is_ok

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy by verifying a 200 response from the /healthyz endpoint.
        
        Args:
            timeout: Maximum time in seconds to wait for a healthy response.
        
        Returns:
            True if the node responds with HTTP 200 before the timeout; otherwise, False.
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
            resp = await asyncio.wait_for(_check_url(url), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        else:
            return resp.status == target
