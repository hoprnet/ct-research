from hoprd_sdk import Configuration, ApiClient
from hoprd_sdk.models import MessagesBody, ChannelsBody
from hoprd_sdk.rest import ApiException
from hoprd_sdk.api import NodeApi, MessagesApi, AccountApi, ChannelsApi, PeersApi
from urllib3.exceptions import MaxRetryError

from .utils import getlogger

log = getlogger()


class HoprdAPIHelper:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self.configuration = Configuration()
        self.configuration.host = f"{url}/api/v3"
        self.configuration.api_key["x-auth-token"] = token

    async def balance(self, type: str = "native"):
        """
        Returns the balance of the node.
        :param: type: str =  "hopr" | "native"
        :return: balance: int
        """

        if type not in ["hopr", "native"]:
            log.error(f"Type `{type}` not supported. Use `hopr` or `native`")
            return None

        log.debug("Getting own balance")

        try:
            with ApiClient(self.configuration) as client:
                account_api = AccountApi(client)
                thread = account_api.account_get_balances(async_req=True)
                response = thread.get()
        except ApiException:
            log.exception("ApiException when calling AccountApi->account_get_balances")
            return None
        except OSError:
            log.exception("OSError when calling AccountApi->account_get_balances")
            return None
        except MaxRetryError:
            log.exception("MaxRetryError when calling AccountApi->account_get_balances")
            return None

        return int(getattr(response, type))

    async def open_channel(self, peer_id: str, amount: int):
        """
        Opens a channel with the given peer_id and amount.
        :param: peer_id: str
        :param: amount: int
        :return: bool
        """
        log.debug(f"Opening channel to '{peer_id}'")

        body = ChannelsBody(peer_id, amount)
        try:
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_open_channel(body, async_req=True)
                response = thread.get()
        except ApiException:
            log.exception(
                "ApiException when calling ChannelsApi->channels_open_channel"
            )
            return False
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_open_channel")
            return False
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_open_channel"
            )
            return False

        if hasattr(response, "channelId"):
            log.debug(f"Channel opened: {response.channelId}")
            return True

        if not hasattr(response, "status"):
            log.error("Can not read `status` from response")
            return False

        if response.status == "CHANNEL_ALREADY_OPEN":
            log.warning(f"Channel could not be opened: {response.status}")
            return True

        log.error(f"Channel could not be opened: {response.status}")
        return False

    async def close_channel(self, channel_id: str):
        """
        Closes a given channel.
        :param: channel_id: str
        :return: bool
        """
        log.debug(f"Closing channel with id {channel_id}")

        try:
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_close_channel(channel_id, async_req=True)
                thread.get()
        except ApiException:
            log.exception(
                "ApiException when calling ChannelsApi->channels_close_channel"
            )
            return False
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_close_channel")
            return False
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_close_channel"
            )
            return False

        return True

    async def incoming_channels(self, only_id: bool = False):
        """
        Returns all open incoming channels.
        :return: channels: list
        """
        log.debug("Getting open channels")

        try:
            async with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_get_channels(async_req=True)
                response = thread.get()
        except ApiException:
            log.exception(
                "ApiException when calling ChannelsApi->channels_get_channels"
            )
            return []
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_get_channels")
            return []
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_get_channels"
            )
            return []

        if not hasattr(response, "incoming"):
            log.warning("Response does not contain `incoming`")
            return []

        if len(response.incoming) == 0:
            log.info("No incoming channels")
            return []

        if only_id:
            return [channel.id for channel in response.incoming]
        else:
            return response.incoming

    async def all_channels(self, include_closed: bool):
        """
        Returns all channels.
        :param: include_closed: bool
        :return: channels: list
        """
        log.debug(f"Getting all channels (include_closed={include_closed})")

        try:
            async with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_get_channels(
                    including_closed=include_closed, async_req=True
                )
                response = thread.get()
        except ApiException:
            log.exception(
                "ApiException when calling ChannelsApi->channels_get_channels"
            )
            return []
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_get_channels")
            return []
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_get_channels"
            )
            return []
        else:
            return response

    async def unique_safe_peerId_links(self):
        """
        Returns a dict containing all unique source_peerId-source_address links.
        """
        log.debug("Getting channel topology")

        try:
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_get_channels(
                    full_topology="true", async_req=True
                )
                response = thread.get()
        except ApiException:
            log.exception(
                "ApiException when calling ChannelsApi->channels_get_channels"
            )
            return None
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_get_channels")
            return None
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_get_channels"
            )
            return None

        if not hasattr(response, "all"):
            log.error("Response does not contain `all`")
            return None

        address_for_peer_id = {}
        for item in response.all:
            if not hasattr(item, "source_peer_id"):
                log.error("Response does not contain `source_peer_id`")
                continue

            if not hasattr(item, "source_address"):
                log.error("Response does not contain `source_address`")
                continue

            address_for_peer_id[item.source_peer_id] = item.source_address

        return address_for_peer_id

    async def ping(self, peer_id: str, metric: str = "latency"):
        """
        Pings the given peer_id and returns the measure.
        :param: peer_id: str
        :param: metric: str = "latency"
        :return: measure: int
        """
        log.debug(f"Pinging peer {peer_id}")

        try:
            with ApiClient(self.configuration) as client:
                peers_api = PeersApi(client)
                thread = peers_api.peers_ping_peer(peer_id, async_req=True)
                response = thread.get()
        except ApiException:
            log.exception("ApiException when calling PeersApi->peers_ping_peer")
            return None
        except OSError:
            log.exception("OSError when calling PeersApi->peers_ping_peer")
            return None
        except MaxRetryError:
            log.exception("MaxRetryError when calling PeersApi->peers_ping_peer")
            return None

        if not hasattr(response, metric):
            log.error(f"No `{metric}` measure from peer {peer_id}")
            return None

        measure = int(getattr(response, metric))

        log.info(f"Measured {measure:3d}({metric}) from peer {peer_id}")
        return measure

    async def peers(
        self, param: str = "peer_id", status: str = "connected", quality: int = 1
    ):
        """
        Returns a list of peers.
        :param: param: str = "peer_id"
        :param: status: str = "connected"
        :param: quality: int = 0..1
        :return: peers: list
        """
        log.debug("Getting peers")

        try:
            with ApiClient(self.configuration) as client:
                node_api = NodeApi(client)
                thread = node_api.node_get_peers(quality=quality, async_req=True)
                response = thread.get()
        except ApiException:
            log.exception("ApiException when calling NodeApi->node_get_peers")
            return []
        except OSError:
            log.exception("OSError when calling NodeApi->node_get_peers")
            return []
        except MaxRetryError:
            log.exception("MaxRetryError when calling NodeApi->node_get_peers")
            return []

        if not hasattr(response, status):
            log.error(f"No `{status}` returned from the API")
            return []

        if len(getattr(response, status)) == 0:
            log.info(f"No peer with status `{status}`")
            return []

        if not hasattr(getattr(response, status)[0], param):
            log.error(f"No param `{param}` found for peers")
            return []

        return [getattr(peer, param) for peer in getattr(response, status)]

    async def get_address(self, address: str):
        """
        Returns the address of the node.
        :param: address: str = "hopr" | "native"
        :return: address: str
        """
        log.debug("Getting address")

        try:
            with ApiClient(self.configuration) as client:
                account_api = AccountApi(client)
                thread = account_api.account_get_address(async_req=True)
                response = thread.get()
        except ApiException:
            log.exception("ApiException when calling AccountApi->account_get_address")
            return None
        except OSError:
            log.exception("OSError when calling AccountApi->account_get_address")
            return None
        except MaxRetryError:
            log.exception("MaxRetryError when calling AccountApi->account_get_address")
            return None

        if not hasattr(response, address):
            log.error(f"No {address} returned from the API")
            return None

        return getattr(response, address)

    async def send_message(
        self, destination: str, message: str, hops: list[str], tag: int = 0x0320
    ) -> bool:
        """
        Sends a message to the given destination.
        :param: destination: str
        :param: message: str
        :param: hops: list[str]
        :param: tag: int = 0x0320
        :return: bool
        """
        log.debug("Sending message")

        body = MessagesBody(tag, message, destination, path=hops)
        try:
            with ApiClient(self.configuration) as client:
                message_api = MessagesApi(client)
                thread = message_api.messages_send_message(body=body, async_req=True)
                thread.get()
        except ApiException:
            log.exception("ApiException when calling MessageApi->messages_send_message")
            return False
        except OSError:
            log.exception("OSError when calling MessageApi->messages_send_message")
            return False
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling MessageApi->messages_send_message"
            )
            return False

        return True
