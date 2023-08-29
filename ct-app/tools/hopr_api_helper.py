import swagger_client as swagger
from swagger_client.rest import ApiException
from urllib3.exceptions import MaxRetryError

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
        configuration = swagger.Configuration()
        configuration.host = f"{url}/api/v2"
        configuration.api_key["x-auth-token"] = token

        api_client = swagger.ApiClient(configuration)
        self.node_api = swagger.NodeApi(api_client)
        self.message_api = swagger.MessagesApi(api_client)
        self.account_api = swagger.AccountApi(api_client)
        self.channels_api = swagger.ChannelsApi(api_client)

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
        except MaxRetryError:
            log.exception("MaxRetryError when calling AccountApi->account_get_balances")
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
        except MaxRetryError:
            log.exception(
                "MaxRetryError when calling ChannelsApi->channels_get_channels"
            )
            return None
        else:
            return response

    async def get_unique_nodeAddress_peerId_aggbalance_links(self):
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
            balance = int(item.balance)

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
        log.debug(f"Pinging peer {peer_id}")

        body = swagger.NodePingBody(peer_id)

        try:
            thread = self.node_api.node_ping(body=body, async_req=True)
            response = thread.get()
        except ApiException:
            log.exception("Exception when calling NodeApi->node_ping")
            return 0
        except OSError:
            log.exception("Exception when calling NodeApi->node_ping")
            return 0
        except MaxRetryError:
            log.exception("MaxRetryError when calling NodeApi->node_ping")
            return 0

        if not hasattr(response, metric):
            log.error(f"No `{metric}` measure from peer {peer_id}")
            return 0

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
        except MaxRetryError:
            log.exception("MaxRetryError when calling NodeApi->node_get_peers")
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
        except MaxRetryError:
            log.exception("MaxRetryError when calling AccountApi->account_get_address")
            return None

        if not hasattr(response, address):
            log.error(f"No {address} returned from the API")
            return None

        return getattr(response, address)

    async def send_message(
        self, destination: str, message: str, hops: list[str]
    ) -> bool:
        log.debug("Sending message")

        body = swagger.MessagesBody(message, destination, path=hops)
        try:
            thread = self.message_api.messages_send_message(body=body, async_req=True)
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
