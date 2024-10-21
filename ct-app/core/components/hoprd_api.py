import asyncio
from typing import Callable, Optional, Union

import aiohttp
import hoprd_sdk as sdk
from urllib3.exceptions import MaxRetryError

from .baseclass import Base
from .channelstatus import ChannelStatus

MESSAGE_TAG = 0x1245


class HoprdAPI(Base):
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        def _refresh_token_hook(self):
            self.api_key["X-Auth-Token"] = token

        self.configuration = sdk.Configuration()
        self.configuration.host = url
        self.configuration.refresh_api_key_hook = _refresh_token_hook

    @property
    def log_prefix(cls) -> str:
        return "api"

    async def __call(
        self,
        obj: Callable[..., object],
        method: str,
        *args,
        **kwargs,
    ):
        kwargs["async_req"] = True
        try:
            with sdk.ApiClient(self.configuration) as client:
                thread = getattr(obj(client), method)(*args, **kwargs)
                response = thread.get()
        except sdk.rest.ApiException as e:
            self.error(
                f"ApiException calling {obj.__name__}.{method} "
                + f"with kwargs: {kwargs}, args: {args}, error is: {e}"
            )
        except OSError:
            self.error(
                f"OSError calling {obj.__name__}.{method} "
                + f"with kwargs: {kwargs}, args: {args}:"
            )
        except MaxRetryError:
            self.error(
                f"MaxRetryError calling {obj.__name__}.{method} "
                + f"with kwargs: {kwargs}, args: {args}"
            )
        except Exception as e:
            self.error(
                f"Exception calling {obj.__name__}.{method} "
                + f"with kwargs: {kwargs}, args: {args}, error is: {e}"
            )
        else:
            return (True, response)

        return (False, None)

    async def __call_api(
        self,
        obj: Callable[..., object],
        method: str,
        call_log: bool = True,
        *args,
        **kwargs,
    ) -> tuple[bool, Optional[object]]:
        if call_log:
            self.debug(
                f"Calling {obj.__name__}.{method} with kwargs: {kwargs}, args: {args}"
            )

        try:
            return await asyncio.wait_for(
                asyncio.create_task(self.__call(obj, method, *args, **kwargs)),
                timeout=60,
            )
        except asyncio.TimeoutError:
            self.error(
                f"TimeoutError calling {obj.__name__}.{method} "
                + f"with kwargs: {kwargs}, args: {args}"
            )
            return (False, None)

    async def balances(self, type: Union[str, list[str]] = "all"):
        """
        Returns the balance of the node.
        :param: type: str =  "all" | "hopr" | "native" | "safe_native" | "safe_hopr"
        :return: balances: dict | int
        """
        all_types = ["hopr", "native", "safe_native", "safe_hopr"]
        if type == "all":
            type = all_types

        elif isinstance(type, str):
            type = [type]

        is_ok, response = await self.__call_api(sdk.api.AccountApi, "balances")

        if not is_ok:
            return {}

        return_dict = {}

        for t in type:
            if not hasattr(response, t):
                self.warning(f"No '{t}' type returned from the API")
                return None

            return_dict[t] = int(getattr(response, t))

        return return_dict if len(return_dict) > 1 else return_dict[type[0]]

    async def open_channel(self, peer_address: str, amount: str):
        """
        Opens a channel with the given peer_address and amount.
        :param: peer_address: str
        :param: amount: str
        :return: channel id: str | undefined
        """
        body = sdk.OpenChannelBodyRequest(amount, peer_address)

        is_ok, response = await self.__call_api(
            sdk.api.ChannelsApi, "open_channel", body=body
        )

        return response.channel_id if is_ok else None

    async def fund_channel(self, channel_id: str, amount: float):
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: float
        :return: bool
        """
        body = sdk.FundBodyRequest(amount=f"{amount:.0f}")
        is_ok, _ = await self.__call_api(
            sdk.api.ChannelsApi, "fund_channel", channel_id=channel_id, body=body
        )

        return is_ok

    async def close_channel(self, channel_id: str):
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        is_ok, _ = await self.__call_api(
            sdk.api.ChannelsApi, "close_channel", channel_id=channel_id
        )
        return is_ok

    async def channels(self, include_closed: bool):
        """
        Returns all channels.
        :param: include_closed: bool
        :return: channels: list
        """
        is_ok, response = await self.__call_api(
            sdk.api.ChannelsApi,
            "list_channels",
            full_topology="true",
            including_closed="true" if include_closed else "false",
        )

        if not is_ok:
            return None

        for channel in response.all:
            channel.status = ChannelStatus.fromString(channel.status)

        return response

    async def peers(
        self,
        params: Union[list, str] = "peer_id",
        status: str = "connected",
        quality: float = 0.5,
    ) -> list[dict]:
        """
        Returns a list of peers.
        :param: param: list or str = "peer_id"
        :param: status: str = "connected"
        :param: quality: int = 0..1
        :return: peers: list
        """
        is_ok, response = await self.__call_api(
            sdk.api.NodeApi, "peers", quality=quality
        )

        if not is_ok:
            return []

        if not hasattr(response, status):
            self.warning(f"No '{status}' field returned from the API")
            return []

        if len(getattr(response, status)) == 0:
            self.warning(f"No peer with state '{status}'")
            return []

        params = [params] if isinstance(params, str) else params
        for param in params:
            if not hasattr(getattr(response, status)[0], param):
                self.warning(f"No param '{param}' found for peers")
                return []

        output_list = []
        for peer in getattr(response, status):
            output_list.append({param: getattr(peer, param) for param in params})

        return output_list

    async def get_address(
        self, address: Union[str, list[str]] = "hopr"
    ) -> Optional[Union[dict[str, str], str]]:
        """
        Returns the address of the node.
        :param: address: str = "hopr" | "native"
        :return: address: str | undefined
        """
        all_types = ["hopr", "native"]

        if address == "all":
            address = all_types
        elif isinstance(address, str):
            address = [address]

        is_ok, response = await self.__call_api(
            sdk.api.AccountApi, "addresses", call_log=False
        )

        if not is_ok:
            return None

        return_dict: dict[str, str] = {}
        for item in address:
            if not hasattr(response, item):
                self.warning(f"No '{item}' address returned from the API")
                return None

            return_dict[item] = getattr(response, item)

        return return_dict if len(return_dict) > 1 else return_dict[address[0]]

    async def send_message(
        self, destination: str, message: str, hops: list[str], tag: int = MESSAGE_TAG
    ) -> bool:
        """
        Sends a message to the given destination.
        :param: destination: str
        :param: message: str
        :param: hops: list[str]
        :param: tag: int = 0x0320
        :return: bool
        """
        body = sdk.SendMessageBodyRequest(message, None, hops, destination, tag)
        is_ok, _ = await self.__call_api(
            sdk.api.MessagesApi, "send_message", call_log=False, body=body
        )

        return is_ok

    async def messages_pop_all(self, tag: int = MESSAGE_TAG) -> list:
        """
        Pop all messages from the inbox
        :param: tag = 0x0320
        :return: list
        """
        body = sdk.TagQueryRequest() if tag is None else sdk.TagQueryRequest(tag=tag)
        _, response = await self.__call_api(sdk.api.MessagesApi, "pop_all", body=body)
        return response.messages if hasattr(response, "messages") else []

    async def node_info(self):
        _, response = await self.__call_api(sdk.api.NodeApi, "info")

        return response

    async def ticket_price(self) -> float:
        _, response = await self.__call_api(sdk.api.NetworkApi, "price")

        return float(response.price) / 1e18 if hasattr(response, "price") else None

    async def healthyz(self, timeout: int = 20) -> bool:
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 after max `timeout` seconds.
        """
        return await HoprdAPI.checkStatus(
            f"{self.configuration.host}/healthyz", 200, timeout
        )

    @classmethod
    async def checkStatus(cls, url: str, target: int, timeout: int = 20) -> bool:
        """
        Checks if the given URL is returning 200 after max `timeout` seconds.
        """

        async def _check_url(url: str):
            while True:
                try:
                    async with aiohttp.ClientSession() as s, s.get(url) as response:
                        return response.status
                except Exception:
                    await asyncio.sleep(0.25)

        try:
            status = await asyncio.wait_for(_check_url(url), timeout=timeout)
        except TimeoutError:
            return False
        except Exception:
            return False
        else:
            return status == target
