from hoprd_sdk import ApiClient, Configuration
from hoprd_sdk.api import (
    AccountApi,
    ChannelsApi,
    MessagesApi,
    NodeApi,
    PeersApi,
)
from hoprd_sdk.models import (
    ChannelidFundBody,
    ChannelsBody,
    MessagesBody,
    MessagesPopBody,
)
from hoprd_sdk.rest import ApiException
from urllib3.exceptions import MaxRetryError

MESSAGE_TAG = 800


class HoprdAPI:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self.configuration = Configuration()
        self.configuration.host = f"{url}/api/v3"
        self.configuration.api_key["x-auth-token"] = token

    def __call_api(self, obj, method, *args, **kwargs):
        try:
            with ApiClient(self.configuration) as client:
                api_callback = obj(client).__getattribute__(method)
                kwargs["async_req"] = True
                thread = api_callback(*args, **kwargs)
                response = thread.get()

                # print(
                #     f"Calling {api_callback.__qualname__} "
                #     + f"with kwargs: {kwargs}, args: {args}, response: {response}"
                # )
                return (True, response)
        except ApiException:
            # print(
            #     f"ApiException calling {api_callback.__qualname__} "
            #     + f"with kwargs: {kwargs}, args: {args}, error is: {e}"
            # )
            return (False, None)
        except OSError:
            # print(
            #     f"OSError calling {api_callback.__qualname__} "
            #     + f"with kwargs: {kwargs}, args: {args}:"
            # )
            return (False, None)
        except MaxRetryError:
            # print(
            #     f"MaxRetryError calling {api_callback.__qualname__} "
            #     + f"with kwargs: {kwargs}, args: {args}"
            # )
            return (False, None)

    async def balances(self):
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

        is_ok, response = self.__call_api(AccountApi, "account_get_balances")
        if not is_ok:
            return None

        return_dict = {}

        for t in type:
            if not hasattr(response, t):
                print(f"No '{t}' type returned from the API")
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
        body = ChannelsBody(peer_address, amount)

        is_ok, response = self.__call_api(
            ChannelsApi, "channels_open_channel", body=body
        )
        return response.channel_id if is_ok else None

    async def fund_channel(self, channel_id: str, amount: str):
        """
        Funds a given channel.
        :param: channel_id: str
        :param: amount: str
        :return: bool
        """
        body = ChannelidFundBody(amount=amount)
        is_ok, _ = self.__call_api(
            ChannelsApi, "channels_fund_channel", channel_id, body=body
        )
        return is_ok

    async def close_channel(self, channel_id: str):
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        is_ok, _ = self.__call_api(ChannelsApi, "channels_close_channel", channel_id)
        return is_ok

    async def incoming_channels(self, only_id: bool = False):
        """
        Returns all open incoming channels.
        :return: channels: list
        """

        is_ok, response = self.__call_api(
            ChannelsApi,
            "channels_get_channels",
            full_topology="false",
            including_closed="false",
        )
        if is_ok:
            if not hasattr(response, "incoming"):
                print("Response does not contain 'incoming'")
                return []

            if len(response.incoming) == 0:
                print("No incoming channels")
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
        is_ok, response = self.__call_api(ChannelsApi, "channels_get_channels")
        if is_ok:
            if not hasattr(response, "outgoing"):
                print("Response does not contain 'outgoing'")
                return []

            if len(response.outgoing) == 0:
                print("No outgoing channels")
                return []

            if only_id:
                return [channel.id for channel in response.outgoing]
            else:
                return response.outgoing
        else:
            return []

    async def get_channel(self, channel_id: str):
        """
        Returns the channel object.
        :param: channel_id: str
        :return: channel: response
        """
        _, response = self.__call_api(ChannelsApi, "channels_get_channel", channel_id)
        return response

    async def all_channels(self, include_closed: bool):
        """
        Returns all channels.
        :param: include_closed: bool
        :return: channels: list
        """
        is_ok, response = self.__call_api(
            ChannelsApi,
            "channels_get_channels",
            full_topology="true",
            including_closed=include_closed,
        )
        return response if is_ok else []

    async def ping(self, peer_id: str):
        """
        Pings the given peer_id and returns the measure.
        :param: peer_id: str
        :return: response: dict
        """
        _, response = self.__call_api(PeersApi, "peers_ping_peer", peer_id)
        return response

    async def peers(
        self,
        params: list or str = "peer_id",
        status: str = "connected",
        quality: float = 0.5,
    ):
        """
        Returns a list of peers.
        :param: param: list or str = "peer_id"
        :param: status: str = "connected"
        :param: quality: int = 0..1
        :return: peers: list
        """

        is_ok, response = self.__call_api(NodeApi, "node_get_peers", quality=quality)
        if not is_ok:
            return []

        if not hasattr(response, status):
            print(f"No '{status}' field returned from the API")
            return []

        if len(getattr(response, status)) == 0:
            print(f"No peer with is_ok '{status}'")
            return []

        params = [params] if isinstance(params, str) else params
        for param in params:
            if not hasattr(getattr(response, status)[0], param):
                print(f"No param '{param}' found for peers")
                return []

        output_list = []
        for peer in getattr(response, status):
            output_list.append({param: getattr(peer, param) for param in params})

        return output_list

    async def get_address(self, address: str or list[str] = "hopr"):
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

        is_ok, response = self.__call_api(AccountApi, "account_get_address")
        if not is_ok:
            return None

        return_dict = {}
        for item in address:
            if not hasattr(response, item):
                print(f"No '{item}' address returned from the API")
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
        body = MessagesBody(tag, message, destination, path=hops)
        is_ok, _ = self.__call_api(MessagesApi, "messages_send_message", body=body)
        return is_ok

    async def messages_pop(self, tag: int = MESSAGE_TAG) -> bool:
        """
        Pop next message from the inbox
        :param: tag = 0x0320
        :return: dict
        """

        body = MessagesPopBody(tag=tag)
        _, response = self.__call_api(MessagesApi, "messages_pop_message", body=body)
        return response
