import asyncio
import json
import logging
from typing import Optional

import aiohttp

from core.components.logs import configure_logging

from . import request_objects as request
from . import response_objects as response
from .http_method import HTTPMethod

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
                logger.exception(
                    "Timeout exception while doing an API call",
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
        Opens a channel with the given peer_address and amount.
        :param: peer_address: str
        :param: amount: str
        :return: channel id: str | undefined
        """
        data = request.OpenChannelBody(amount, peer_address)

        is_ok, resp = await self.__call_api(
            HTTPMethod.POST, "channels", data, timeout=90
        )
        return response.OpenedChannel(resp) if is_ok else None

    async def fund_channel(self, channel_id: str, amount: float) -> bool:
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: float
        :return: bool
        """
        data = request.FundChannelBody(amount)

        is_ok, _ = await self.__call_api(
            HTTPMethod.POST, f"channels/{channel_id}/fund", data, timeout=90
        )
        return is_ok

    async def close_channel(self, channel_id: str) -> bool:
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        is_ok, _ = await self.__call_api(
            HTTPMethod.DELETE, f"channels/{channel_id}", timeout=90
        )
        return is_ok

    async def channels(self) -> response.Channels:
        """
        Returns all channels.
        :return: channels: list
        """
        params = request.GetChannelsBody("true", "false")

        is_ok, resp = await self.__call_api(
            HTTPMethod.GET, f"channels?{params.as_header_string}"
        )
        return response.Channels(resp) if is_ok else None

    async def peers(
        self,
        quality: float = 0.5,
    ) -> list[response.ConnectedPeer]:
        """
        Returns a list of peers.
        :param: param: list or str = "peerId"
        :param: status: str = "connected"
        :param: quality: int = 0..1
        :return: peers: list
        """
        params = request.GetPeersBody(quality)

        is_ok, resp = await self.__call_api(
            HTTPMethod.GET, f"node/peers?{params.as_header_string}"
        )

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

    async def send_message(
        self, destination: str, message: str, hops: list[str], tag: int = MESSAGE_TAG
    ) -> Optional[response.SendMessageAck]:
        """
        Sends a message to the given destination.
        :param: destination: str
        :param: message: str
        :param: hops: list[str]
        :param: tag: int = 0x0320
        :return: bool
        """
        data = request.SendMessageBody(message, hops, destination, tag)
        is_ok, resp = await self.__call_api(HTTPMethod.POST, "messages", data=data)
        return response.SendMessageAck(resp) if is_ok else None

    async def node_info(self) -> Optional[response.Infos]:
        """
        Gets informations about the HOPRd node.
        :return: Infos
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "node/info")
        return response.Infos(resp) if is_ok else None

    async def ticket_price(self) -> Optional[response.TicketPrice]:
        """
        Gets the ticket price set in the configuration file.
        :return: TicketPrice
        """
        is_ok, resp = await self.__call_api(HTTPMethod.GET, "node/configuration")
        return (
            response.TicketPrice(response.Configuration(json.loads(resp)).as_dict)
            if is_ok
            else None
        )

    async def messages_pop_all(self, tag: int = MESSAGE_TAG) -> list:
        """
        Pop all messages from the inbox
        :param: tag = 0x0320
        :return: list
        """
        is_ok, resp = await self.__call_api(
            HTTPMethod.POST, "messages/pop-all", data=request.PopMessagesBody(tag)
        )
        return (
            [response.Message(item) for item in resp.get("messages", [])]
            if is_ok
            else []
        )

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
            resp = await asyncio.wait_for(_check_url(url), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        else:
            return resp.status == target
