import json
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

    async def balances(self, type: str or list[str] = "all"):
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

        for t in type:
            if t not in all_types:
                log.error(
                    f"Type `{type}` not supported. Use `all`, `hopr`, `native`, "
                    + "`safeNative` or `safeHopr`"
                )
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

        return_dict = {}

        for t in type:
            return_dict[t] = int(getattr(response, t))

        return return_dict if len(return_dict) > 1 else return_dict[type[0]]

    async def open_channel(self, peer_address: str, amount: int):
        """
        Opens a channel with the given peer_address and amount.
        :param: peer_address: str
        :param: amount: int
        :return: bool
        """
        log.debug(f"Opening channel to '{peer_address}'")

        status = None
        body = ChannelsBody(peer_address, amount)
        try:
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_open_channel(body=body, async_req=True)
                response = thread.get()
        except ApiException as e:
            log.error("ApiException when calling ChannelsApi->channels_open_channel")
            status = json.loads(e.body.decode())["status"]
        except OSError:
            log.error("OSError when calling ChannelsApi->channels_open_channel")
            return False
        except MaxRetryError:
            log.error("MaxRetryError when calling ChannelsApi->channels_open_channel")
            return False

        if status == "CHANNEL_ALREADY_OPEN":
            log.warning("Channel already opened")
            return True

        if hasattr(response, "channelId"):
            log.debug(f"Channel opened: {response.channelId}")
            return True

        if not hasattr(response, "status"):
            log.error("Can not read `status` from response")
            return False

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
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_get_channels(
                    full_topology="false", including_closed="false", async_req=True
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
            with ApiClient(self.configuration) as client:
                channels_api = ChannelsApi(client)
                thread = channels_api.channels_get_channels(
                    full_topology="true",
                    including_closed=include_closed,
                    async_req=True,
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

    # async def native_address_from_peer_id(self, peer_id: str):
    #     """
    #     Returns the native address of the given peer_id.
    #     :param: peer_id: str
    #     :return: address: str
    #     """
    #     log.debug(f"Getting native address from peer id {peer_id}")

    #     try:
    #         with ApiClient(self.configuration) as client:
    #             peers_api = PeersApi(client)
    #             thread = peers_api.peers_get_peer(peer_id, async_req=True)
    #             response = thread.get()
    #     except ApiException:
    #         log.exception("ApiException when calling PeersApi->peers_get_peer")
    #         return None
    #     except OSError:
    #         log.exception("OSError when calling PeersApi->peers_get_peer")
    #         return None
    #     except MaxRetryError:
    #         log.exception("MaxRetryError when calling PeersApi->peers_get_peer")
    #         return None

    #     if not hasattr(response, "address"):
    #         log.error("Response does not contain `address`")
    #         return None

    #     return getattr(response, "address")

    async def get_unique_nodeAddress_peerId_aggbalance_links(self):
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

        peerid_address_aggbalance_links = {}
        for item in response.all:
            if not hasattr(item, "source_peer_id") or not hasattr(
                item, "source_address"
            ):
                log.error(
                    "Response does not contain `source_peerid` or `source_address`"
                )
                continue

            if not hasattr(item, "status"):
                log.error("Response does not contain `status`")
                continue

            source_peer_id = item.source_peer_id
            source_address = item.source_address
            balance = int(item.balance) / 1e18

            if item.status != "Open":
                # Other Statuses: "Waiting for commitment", "Closed", "Pending to close"
                # Ensures that nodes must have at least 1 open channel in to receive ct
                continue

            if source_peer_id not in peerid_address_aggbalance_links:
                peerid_address_aggbalance_links[source_peer_id] = {
                    "source_node_address": source_address,
                    "aggregated_balance": balance,
                }

            else:
                peerid_address_aggbalance_links[source_peer_id][
                    "aggregated_balance"
                ] += balance

        return peerid_address_aggbalance_links

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
            return 0
        except OSError:
            log.exception("OSError when calling PeersApi->peers_ping_peer")
            return 0
        except MaxRetryError:
            log.exception("MaxRetryError when calling PeersApi->peers_ping_peer")
            return 0

        if not hasattr(response, metric):
            log.error(f"No `{metric}` measure from peer {peer_id}")
            return 0

        measure = int(getattr(response, metric))

        log.debug(f"Measured {measure:3d}({metric}) from peer {peer_id}")
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
