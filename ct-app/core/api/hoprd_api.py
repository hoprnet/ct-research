import asyncio
import logging
from typing import Callable, Optional, Union

import aiohttp

from ..components.balance import Balance
from ..components.logs import configure_logging
from . import request_objects as req
from . import response_objects as resp
from .http_method import HTTPMethod
from .protocol import Protocol

configure_logging()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class HoprdAPI:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: Optional[str] = None):
        self.host = url
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.prefix = "/api/v4/"

    async def __call(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: Optional[req.ApiRequestObject] = None,
        use_api_path: bool = True,
    ):
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
                    url=f"{self.host}{self.prefix if use_api_path else '/'}{endpoint}",
                    json={} if data is None else data.as_dict,
                    headers=headers,
                ) as res:
                    try:
                        data = await res.json()
                    except Exception:
                        data = await res.text()

                    return int(res.status // 200) == 1, data
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

    async def __call_api_with_timeout(
        self,
        method: HTTPMethod,
        endpoint: str,
        data: Optional[req.ApiRequestObject] = None,
        timeout: int = 90,
        use_api_path: bool = True,
    ) -> tuple[bool, Optional[object]]:
        backoff = 0.5
        while True:
            try:
                result = await asyncio.wait_for(
                    asyncio.create_task(self.__call(method, endpoint, data, use_api_path)),
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

    async def request(
        self,
        method: HTTPMethod,
        path: str,
        data: Optional[req.ApiRequestObject] = None,
        resp_type: Optional[Callable] = None,
        use_api_path: bool = True,
        return_state: bool = False,
        timeout: int = 90,
    ) -> Optional[Union[resp.ApiResponseObject, dict]]:
        is_ok, r = await self.__call_api_with_timeout(
            method, path, data, timeout=timeout, use_api_path=use_api_path
        )

        if not is_ok:
            if r is None:
                logger.error(
                    "API request failed due to timeout", {"method": method.value, "path": path}
                )
            else:
                logger.error("API request failed", {"method": method.value, "path": path, "r": r})

        if return_state:
            return is_ok

        if not is_ok:
            return None

        if resp_type is None:
            return r

        return resp_type(r)

    async def balances(self) -> Optional[resp.Balances]:
        """
        Returns the balance of the node.
        :return: balances: Balances | undefined
        """
        return await self.request(HTTPMethod.GET, "account/balances", resp_type=resp.Balances)

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
        return await self.request(HTTPMethod.POST, "channels", data, resp_type=resp.OpenedChannel)

    async def fund_channel(self, channel_id: str, amount: Balance) -> bool:
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: Balance
        :return: bool
        """
        data = req.FundChannelBody(amount.as_str)
        return await self.request(
            HTTPMethod.POST, f"channels/{channel_id}/fund", data, return_state=True
        )

    async def close_channel(self, channel_id: str) -> bool:
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        return await self.request(HTTPMethod.DELETE, f"channels/{channel_id}", return_state=True)

    async def channels(self, full_topology: bool = True) -> Optional[resp.Channels]:
        """
        Returns all channels.
        :return: channels: list
        """
        header = req.GetChannelsBody(full_topology, False).as_header_string
        return await self.request(HTTPMethod.GET, f"channels?{header}", resp_type=resp.Channels)

    async def metrics(self) -> Optional[resp.Metrics]:
        """
        Returns the metrics of the node.
        :return: metrics: list
        """
        return await self.request(
            HTTPMethod.GET, "metrics", resp_type=resp.Metrics, use_api_path=False
        )

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

        if r := await self.request(HTTPMethod.GET, f"node/peers?{params.as_header_string}"):
            return [resp.ConnectedPeer(peer) for peer in r.get(status, [])]
        else:
            return []

    async def address(self) -> Optional[resp.Addresses]:
        """
        Returns the address of the node.
        :return: address: Addresses | undefined
        """
        return await self.request(HTTPMethod.GET, "account/addresses", resp_type=resp.Addresses)

    async def node_info(self) -> Optional[resp.Infos]:
        """
        Gets informations about the HOPRd node.
        :return: Infos
        """
        return await self.request(HTTPMethod.GET, "node/info", resp.Infos)

    async def ticket_price(self) -> Optional[resp.TicketPrice]:
        """
        Gets the ticket price set in the configuration file.
        :return: TicketPrice
        """

        if config := await self.request(
            HTTPMethod.GET, "node/configuration", resp_type=resp.Configuration
        ):
            price = resp.TicketPrice(config.as_dict)
        else:
            price = None

        if price and price.value != "None":
            return price

        return await self.request(HTTPMethod.GET, "network/price", resp.TicketPrice)

    async def list_sessions(self, protocol: Protocol = Protocol.UDP) -> list[resp.Session]:
        """
        Lists existing Session listeners for the given IP protocol
        :param: protocol: Protocol
        :return: list[Session]
        """
        if r := await self.request(HTTPMethod.GET, f"session/{protocol.name.lower()}"):
            return [resp.Session(s) for s in r]
        else:
            return []

    async def post_session(
        self,
        destination: str,
        relayer: str,
        listen_host: str = ":0",
        protocol: Protocol = Protocol.UDP,
    ) -> Union[resp.Session, resp.SessionFailure]:
        """
        Creates a new session returning the session listening host & port over TCP or UDP.
        :param: destination: Address of the recipient
        :param: relayer: Address of the relayer
        :param: listen_host: str
        :param: protocol: Protocol (UDP or TCP)
        :return: Session
        """
        capabilities_body = req.SessionCapabilitiesBody(protocol.retransmit, protocol.segment)
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
        if r := await self.request(
            HTTPMethod.POST,
            f"session/{protocol.name.lower()}",
            data,
            timeout=5,
            resp_type=resp.Session,
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
        return await self.request(HTTPMethod.DELETE, session.as_path, return_state=True)

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 before timeout.
        """
        try:
            is_ok = await asyncio.wait_for(self._check_url("healthyz"), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        else:
            return is_ok

    async def _check_url(self, url: str):
        while True:
            try:
                return await self.request(
                    HTTPMethod.GET, url, use_api_path=False, return_state=True, timeout=None
                )
            except Exception:
                await asyncio.sleep(0.25)
