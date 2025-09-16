import logging
from datetime import datetime
from typing import Optional

from api_lib.headers.authorization import Bearer
from prometheus_client import Gauge

from . import mixins
from .api.hoprd_api import HoprdAPI
from .components.asyncloop import AsyncLoop
from .components.balance import Balance
from .components.config_parser import Parameters
from .components.logs import configure_logging
from .components.peer import Peer
from .components.utils import Utils
from .rpc import entries as rpc_entries
from .subgraph import entries as subgraph_entries

BALANCE_MULTIPLIER = Gauge("ct_balance_multiplier", "factor to multiply the balance by")

configure_logging()
logger = logging.getLogger(__name__)


class Node(
    mixins.ChannelMixin,
    mixins.EconomicSystemMixin,
    mixins.NftMixin,
    mixins.PeersMixin,
    mixins.RPCMixin,
    mixins.SubgraphMixin,
    mixins.SessionMixin,
    mixins.StateMixin,
):
    def __init__(self, url: str, key: str, params: Optional[Parameters] = None):
        """
        Create a new Node with the specified url and key.
        :param url: The url of the node.
        :param key: The key of the node.
        """
        self.api = HoprdAPI(url, Bearer(key), "/api/v4")
        self.url = url

        self.peers = set[Peer]()
        self.peer_history = dict[str, datetime]()
        self.session_destinations = list[str]()

        self.address = None
        self.channels = None

        self.topology_data = dict[str, Balance]()
        self.registered_nodes_data = list[subgraph_entries.Node]()
        self.nft_holders_data = list[str]()
        self.allocations_data = list[rpc_entries.Allocation]()
        self.eoa_balances_data = list[rpc_entries.ExternalBalance]()
        self.peers_rewards_data = dict[str, float]()

        self.ticket_price = None

        self.params = params or Parameters()

        self.connected = False
        self.running = True

        BALANCE_MULTIPLIER.set(1.0)

    async def start(self):
        await self.retrieve_address()

        self.get_graphql_providers()
        self.get_nft_holders()

        keep_alive_methods: list[str] = Utils.get_methods(mixins.__path__[0], "keepalive")
        AsyncLoop.update([getattr(self, m) for m in keep_alive_methods])

        await AsyncLoop.gather()

    def stop(self):
        self.running = False
