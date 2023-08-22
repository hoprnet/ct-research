from hoprd_sdk import Configuration, ApiClient
from hoprd_sdk.models import MessageBody
from hoprd_sdk.rest import ApiException
from hoprd_sdk.api import NodeApi, MessagesApi, AccountApi, ChannelsApi, PeersApi

from .utils import getlogger

log = getlogger()


class HoprdAPIHelper:
    """
    HOPRd API helper to handle exceptions and logging.
    """

    def __init__(self, url: str, token: str):
        self._setup(url, token)

        self._url = url
        self._token = token

    def _setup(self, url: str, token: str):
        configuration = Configuration()
        configuration.host = f"{url}/api/v2"
        configuration.api_key["x-auth-token"] = token

        self.node_api = NodeApi(ApiClient(configuration))
        self.peers_api = PeersApi(ApiClient(configuration))
        self.message_api = MessagesApi(ApiClient(configuration))
        self.account_api = AccountApi(ApiClient(configuration))
        self.channels_api = ChannelsApi(ApiClient(configuration))

    @property
    def url(self) -> str:
        return self._url

    @property
    def token(self) -> str:
        return self._token

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
            thread = self.account_api.account_get_balances(async_req=True)
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling AccountApi->account_get_balances")
            return None
        except OSError:
            log.exception("Exception when calling AccountApi->account_get_balances")
            return None

        return int(getattr(response, type))

    async def get_all_channels(self, include_closed: bool):
        log.debug("Getting all channels")

        try:
            thread = self.channels_api.channels_get_channels(
                including_closed=include_closed, async_req=True
            )
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling ChannelsApi->channels_get_channels")
            return None
        except OSError:
            log.exception("Exception when calling ChannelsApi->channels_get_channels")
            return None
        else:
            return response

    async def get_unique_safe_peerId_links(self):
        """
        Returns a dict containing all unique source_peerId-source_address links.
        """

        log.debug("Getting channel topology")

        try:
            thread = self.channels_api.channels_get_channels(
                full_topology="true", async_req=True
            )
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling ChannelsApi->channels_get_channels")
            return None
        except OSError:
            log.exception("Exception when calling ChannelsApi->channels_get_channels")
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
            thread = self.peers_api.peers_ping_peer(peer_id, async_req=True)
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling PeersApi->peers_ping_peer")
            return None
        except OSError:
            log.exception("Exception when calling PeersApi->peers_ping_peer")
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
            thread = self.node_api.node_get_peers(quality=quality, async_req=True)
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling NodeApi->node_get_peers")
            return []
        except OSError:
            log.exception("Exception when calling NodeApi->node_get_peers")
            return []

        if not hasattr(response, status):
            log.error(f"No `{status}` from {self.url}")
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
            thread = self.account_api.account_get_address(async_req=True)
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling AccountApi->account_get_address")
            return None
        except OSError:
            log.exception("Exception when calling AccountApi->account_get_address")
            return None

        if not hasattr(response, address):
            log.error(f"No {address} returned from the API")
            return None

        return getattr(response, address)

    async def send_message(
        self, destination: str, message: str, hops: list[str]
    ) -> bool:
        log.debug("Sending message")

        body = MessageBody(message, destination, path=hops)
        try:
            thread = self.message_api.messages_send_message(body=body, async_req=True)
            thread.get()
        except ApiException:
            log.exception("Exception when calling MessageApi->messages_send_message")
            return False
        except OSError:
            log.exception("Exception when calling MessageApi->messages_send_message")
            return False

        return True
