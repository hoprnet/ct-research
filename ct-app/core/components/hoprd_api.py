import asyncio
from typing import Callable, Optional, Union

import requests
from hoprd_sdk import (
    ApiClient,
    Configuration,
    FundBodyRequest,
    OpenChannelBodyRequest,
    SendMessageBodyRequest,
    TagQueryRequest,
)
from hoprd_sdk.api import AccountApi, ChannelsApi, MessagesApi, NetworkApi, NodeApi
from hoprd_sdk.rest import ApiException
from requests import Response
from urllib3.exceptions import MaxRetryError

from .baseclass import Base

MESSAGE_TAG = 800


class HoprdAPI(Base):
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        def _refresh_token_hook(self):
            self.api_key["X-Auth-Token"] = token

        self.configuration = Configuration()
        self.configuration.host = f"{url}"
        self.configuration.refresh_api_key_hook = _refresh_token_hook

    @property
    def print_prefix(cls) -> str:
        return "api"

    async def __call_api(
        self,
        obj: Callable[..., object],
        method: str,
        *args,
        **kwargs,
    ) -> tuple[bool, Optional[object]]:
        async def __call(
            obj: Callable[..., object],
            method: str,
            *args,
            **kwargs,
        ):
            try:
                with ApiClient(self.configuration) as client:
                    api_callback = getattr(obj(client), method)
                    kwargs["async_req"] = True
                    thread = api_callback(*args, **kwargs)
                    response = thread.get()

            except ApiException as e:
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

        try:
            return await asyncio.wait_for(
                asyncio.create_task(__call(obj, method, *args, **kwargs)),
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

        is_ok, response = await self.__call_api(AccountApi, "balances")

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
        body = OpenChannelBodyRequest(amount, peer_address)

        is_ok, response = await self.__call_api(ChannelsApi, "open_channel", body=body)

        return response.channel_id if is_ok else None

    async def fund_channel(self, channel_id: str, amount: float):
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: float
        :return: bool
        """
        body = FundBodyRequest(amount=f"{amount:.0f}")
        is_ok, _ = await self.__call_api(
            ChannelsApi, "fund_channel", channel_id=channel_id, body=body
        )

        return is_ok

    async def close_channel(self, channel_id: str):
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        is_ok, _ = await self.__call_api(
            ChannelsApi, "close_channel", channel_id=channel_id
        )
        return is_ok

    async def incoming_channels(self, only_id: bool = False) -> list:
        """
        Returns all open incoming channels.
        :return: channels: list
        """

        is_ok, response = await self.__call_api(
            ChannelsApi,
            "list_channels",
            full_topology=False,
            including_closed=False,
        )
        if is_ok:
            if not hasattr(response, "incoming"):
                self.warning("Response does not contain 'incoming'")
                return []

            if len(response.incoming) == 0:
                self.warning("No incoming channels")
                return []

            if only_id:
                return [channel.id for channel in response.incoming]
            else:
                return response.incoming
        else:
            return []

    async def outgoing_channels(self, only_id: bool = False):
        """
        Returns all open outgoing channels.
        :return: channels: list
        """
        is_ok, response = await self.__call_api(
            ChannelsApi,
            "list_channels",
            full_topology=False,
            including_closed=False,
        )
        if is_ok:
            if not hasattr(response, "outgoing"):
                self.warning("Response does not contain 'outgoing'")
                return []

            if len(response.outgoing) == 0:
                self.warning("No outgoing channels")
                return []

            if only_id:
                return [channel.id for channel in response.outgoing]
            else:
                return response.outgoing
        else:
            return []

    async def all_channels(self, include_closed: bool):
        """
        Returns all channels.
        :param: include_closed: bool
        :return: channels: list
        """
        is_ok, response = await self.__call_api(
            ChannelsApi,
            "list_channels",
            full_topology="true",
            including_closed="true" if include_closed else "false",
        )

        return response if is_ok else []

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
        is_ok, response = await self.__call_api(NodeApi, "peers", quality=quality)

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

        is_ok, response = await self.__call_api(AccountApi, "addresses")

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
        body = SendMessageBodyRequest(message, None, hops, destination, tag)
        is_ok, _ = await self.__call_api(MessagesApi, "send_message", body=body)

        return is_ok

    async def messages_pop(self, tag: int = None) -> bool:
        """
        Pop next message from the inbox
        :param: tag = 0x0320
        :return: dict
        """
        body = TagQueryRequest() if tag is None else TagQueryRequest(tag=tag)
        _, response = await self.__call_api(MessagesApi, "pop", body=body)

        return response

    async def messages_pop_all(self, tag: int = None) -> list:
        """
        Pop all messages from the inbox
        :param: tag = 0x0320
        :return: list
        """
        body = TagQueryRequest() if tag is None else TagQueryRequest(tag=tag)
        _, response = await self.__call_api(MessagesApi, "pop_all", body=body)
        return response.messages if hasattr(response, "messages") else []

    async def node_info(self):
        _, response = await self.__call_api(NodeApi, "info")

        return response

    async def ticket_price(self) -> int:
        _, response = await self.__call_api(NetworkApi, "price")

        return float(response.price) / 1e18 if hasattr(response, "price") else None

    async def channel_balance(self, src_peer_id: str, dest_peer_id: str) -> float:
        """
        Get the channel balance of a given address.
        :param api: API helper instance.
        :param src_peer_id: Source channel peer id.
        :param dest_peer_id: Destination channel peer id.
        :return: Channel balance of the address.
        """
        channels = await self.all_channels(False)

        channel = [
            c
            for c in channels.all
            if c.destination_peer_id == dest_peer_id
            and c.source_peer_id == src_peer_id
            and c.status == "Open"
        ]

        return 0 if len(channel) == 0 else int(channel[0].balance) / 1e18

    async def startedz(self, timeout: int = 20):
        """
        Checks if the node is started. Return True if `startedz` returns 200 after max `timeout` seconds.
        """
        return await is_url_returning_200(
            f"{self.configuration.host}/startedz", timeout
        )

    async def readyz(self, timeout: int = 20):
        """
        Checks if the node is ready. Return True if `readyz` returns 200 after max `timeout` seconds.
        """
        return await is_url_returning_200(f"{self.configuration.host}/readyz", timeout)

    async def healthyz(self, timeout: int = 20):
        """
        Checks if the node is healthy. Return True if `healthyz` returns 200 after max `timeout` seconds.
        """
        return await is_url_returning_200(
            f"{self.configuration.host}/healthyz", timeout
        )


async def is_url_returning_200(url: str, timeout: int = 20) -> Response:
    """
    Checks if the given URL is returning 200 after max `timeout` seconds.
    """

    async def _check_url(url: str):
        while True:
            try:
                req = requests.get(url)
                return req
            except Exception:
                await asyncio.sleep(0.25)

    try:
        result = await asyncio.wait_for(_check_url(url), timeout=timeout)
    except TimeoutError:
        return False
    else:
        return result.status_code == 200
