from hoprd_sdk import Configuration, ApiClient
from hoprd_sdk.models import MessagesBody
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

        log.debug("Getting balance")

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

    async def get_all_channels(self, include_closed: bool):
        log.debug("Getting all channels")

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
            return None
        except OSError:
            log.exception("OSError when calling ChannelsApi->channels_get_channels")
            return None
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_get_channels"
            )
            return None
        else:
            return response

    async def get_unique_safe_peerId_links(self):
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
