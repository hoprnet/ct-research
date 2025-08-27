import logging
from datetime import datetime
from typing import Optional

from api_lib.headers.authorization import Bearer

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
        self.api: HoprdAPI = HoprdAPI(url, Bearer(key), "/api/v4")
        self.url = url

        self.peers = set[Peer]()
        self.peer_history = dict[str, datetime]()
        self.session_destinations: list[str] = []

        self.address = None
        self.channels = None

        self.topology_data = dict[str, Balance]()
        self.registered_nodes_data = list[subgraph_entries.Node]()
        self.nft_holders_data = list[str]()
        self.allocations_data = list[rpc_entries.Allocation]()
        self.eoa_balances_data = list[rpc_entries.ExternalBalance]()
        self.peers_rewards_data = dict[str, float]()

        self.ticket_price = None

        self.params = params if params else Parameters()

        self.connected = False
        self.running = True

    async def start(self):
        logger.info("CT started")

        await self.retrieve_address()

        self.get_graphql_providers()
        self.get_nft_holders()
        await self.close_all_sessions()

        tasks = [getattr(self, m) for m in Utils.get_methods(mixins.__path__[0], "keepalive")]
        AsyncLoop.update(tasks)

        await AsyncLoop.gather()

    def stop(self):
        logger.info("CT stopped")
        self.running = False
