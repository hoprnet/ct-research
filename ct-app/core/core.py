# region Imports
import logging
import random
from typing import Callable

from prometheus_client import Gauge

from core.api.response_objects import TicketPrice
from core.components.balance import Balance
from core.components.config_parser import LegacyParams, SigmoidParams
from core.components.logs import configure_logging
from core.subgraph import GraphQLProvider

from .api import HoprdAPI
from .components import Address, AsyncLoop, LockedVar, Peer, Utils
from .components.config_parser import Parameters
from .components.decorators import keepalive
from .node import Node
from .subgraph import URL, Type, entries

# endregion

# region Metrics
BALANCE_MULTIPLIER = Gauge("ct_balance_multiplier", "factor to multiply the balance by")
ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["address", "model"]
)
NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")
REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])
STAKE = Gauge("ct_peer_stake", "Stake", ["safe", "type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])
# endregion

configure_logging()
logger = logging.getLogger(__name__)


class Core:
    """
    The Core class represents the main class of the application. It is responsible for managing
    the nodes, the economic model and the distribution of rewards.
    """

    def __init__(self, nodes: list[Node], params: Parameters):
        super().__init__()

        self.params = params
        self.nodes = nodes
        for node in self.nodes:
            node.params = params

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_data = list[entries.Topology]()
        self.registered_nodes_data = list[entries.Node]()
        self.nft_holders_data = list[str]()
        self.peers_rewards_data = dict[str, float]()
        self.ticket_price: TicketPrice = None

        # Initialize the providers
        user_id = self.params.subgraph.user_id
        api_key = self.params.subgraph.api_key
        self.providers: dict[Type, GraphQLProvider] = {
            s: s.provider(URL(user_id, api_key, getattr(self.params.subgraph, s.value)))
            for s in Type
        }

        self.running = True

        BALANCE_MULTIPLIER.set(1)

    @property
    def api(self) -> HoprdAPI:
        return random.choice(self.nodes).api

    @property
    def channels(self):
        return random.choice(self.nodes).channels

    @property
    def ct_nodes_addresses(self) -> list[Address]:
        return [node.address for node in self.nodes]

    @keepalive
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph mode in use (default, backup or none).
        """
        logger.info("Rotating subgraphs")
        for provider in self.providers.values():
            await provider.test(self.params.subgraph.type)

    @keepalive
    async def connected_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """

        counts = {"new": 0, "known": 0, "unreachable": 0}

        async with self.all_peers as current_peers:
            visible_peers: set[Peer] = set()
            visible_peers.update(*[await node.peers.get() for node in self.nodes])
            visible_peers: list[Peer] = list(visible_peers)

            for peer in current_peers:
                # if peer is still visible
                if peer in visible_peers:
                    if peer.yearly_message_count is None:
                        peer.yearly_message_count = 0
                        peer.start_async_processes()
                    counts["known"] += 1

                # if peer is not visible anymore
                else:
                    peer.yearly_message_count = None
                    peer.running = False
                    counts["unreachable"] += 1

            # if peer is new
            for peer in visible_peers:
                if peer not in current_peers:
                    peer.params = self.params
                    peer.yearly_message_count = 0
                    peer.start_async_processes()
                    current_peers.add(peer)
                    counts["new"] += 1

            logger.debug("Aggregated peers from all running nodes", counts)

            for key, value in counts.items():
                UNIQUE_PEERS.labels(key).set(value)

    @keepalive
    async def registered_nodes(self):
        """
        Gets all registered nodes in the Network Registry.
        """

        results = list[entries.Node]()
        for safe in await self.providers[Type.SAFES].get():
            results.extend(
                [
                    entries.Node.fromSubgraphResult(node)
                    for node in safe["registeredNodesInSafeRegistry"]
                ]
            )

        for node in results:
            STAKE.labels(node.safe.address, "balance").set(float(node.safe.balance.value))
            STAKE.labels(node.safe.address, "allowance").set(float(node.safe.allowance.value))

        self.registered_nodes_data = results
        logger.debug("Fetched registered nodes in the safe registry", {"count": len(results)})
        SUBGRAPH_SIZE.set(len(results))

    @keepalive
    async def nft_holders(self):
        """
        Gets all NFT holders.
        """
        # TODO: get this from a static file
        results = list[str]()
        NFT_HOLDERS.set(len(results))

    @keepalive
    async def topology(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """

        channels = self.channels
        if channels is None or channels.all is None:
            logger.warning("No topological data available")
            return

        self.topology_data = [
            entries.Topology(address, balance)
            for address, balance in (await Utils.balanceInChannels(channels.all)).items()
        ]

        logger.debug("Fetched all topology links", {"count": len(self.topology_data)})
        TOPOLOGY_SIZE.set(len(self.topology_data))

    @keepalive
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        async with self.all_peers as peers:
            if not all([len(self.topology_data), len(self.registered_nodes_data), len(peers)]):
                logger.warning("Not enough data to apply economic model")
                return

            await Utils.mergeDataSources(self.topology_data, peers, self.registered_nodes_data)

            Utils.allowManyNodePerSafe(peers)

            for p in peers:
                if not p.is_eligible(
                    self.params.economic_model.min_safe_allowance,
                    self.params.economic_model.legacy.coefficients.lowerbound,
                    self.ct_nodes_addresses,
                    self.nft_holders_data,
                    self.params.economic_model.nft_threshold,
                ):
                    p.yearly_message_count = None

            economic_security = (
                sum(
                    [p.split_stake for p in peers if p.yearly_message_count is not None],
                    Balance.zero("wxHOPR"),
                )
                / self.params.economic_model.sigmoid.total_token_supply
            )
            network_capacity = (
                len([p for p in peers if p.yearly_message_count is not None])
                / self.params.economic_model.sigmoid.network_capacity
            )

            message_count = {SigmoidParams: 0, LegacyParams: 0}
            model_input = {SigmoidParams: [], LegacyParams: []}
            model_input[SigmoidParams] = [economic_security, network_capacity]

            for peer in peers:
                if peer.yearly_message_count is None:
                    continue

                model_input[LegacyParams] = self.peers_rewards_data.get(peer.address.native, 0.0)

                for name, model in self.params.economic_model.models.items():
                    message_count[model.__class__] = model.yearly_message_count(
                        peer.split_stake,
                        self.ticket_price,
                        model_input[model.__class__],
                    )

                    MESSAGE_COUNT.labels(peer.address.native, name).set(
                        message_count[model.__class__]
                    )

                peer.yearly_message_count = sum(message_count.values())

            eligible_count = sum([p.yearly_message_count is not None for p in peers])
            logger.info("Generated the eligible nodes set", {"count": eligible_count})
            ELIGIBLE_PEERS.set(eligible_count)

    @keepalive
    async def peers_rewards(self):
        results = dict()
        for acc in await self.providers[Type.REWARDS].get():
            account = entries.Account.fromSubgraphResult(acc)
            results[account.address] = account.redeemed_value
            REDEEMED_REWARDS.labels(account.address).set(account.redeemed_value)

        self.peers_rewards_data = results
        logger.debug("Fetched peers rewards amounts", {"count": len(results)})

    @keepalive
    async def ticket_parameters(self):
        """
        Gets the ticket price from the api.
        They are used in the economic model to calculate the number of messages to send to a peer.
        """
        ticket_price = await self.api.ticket_price()

        logger.debug(
            "Fetched ticket price",
            {"value": str(getattr(getattr(ticket_price, "value", None), "value", None))},
        )

        if ticket_price is not None:
            self.ticket_price = ticket_price
            TICKET_STATS.labels("price").set(ticket_price.value.value)

    @keepalive
    async def open_sessions(self):
        """
        Opens sessions for all eligible peers.
        """
        eligible_addresses = [
            peer.address
            for peer in await self.all_peers.get()
            if peer.yearly_message_count is not None
        ]
        for node in self.nodes:
            await node.open_sessions(eligible_addresses, self.ct_nodes_addresses)

    @property
    def tasks(self) -> list[Callable]:
        return [getattr(self, method) for method in Utils.decorated_methods(__file__, "keepalive")]

    async def start(self):
        """
        Start the node.
        """
        logger.info("CTCore started", {"num_nodes": len(self.nodes)})

        await AsyncLoop.gather_any([node._healthcheck() for node in self.nodes])
        await AsyncLoop.gather_any([node.close_all_sessions() for node in self.nodes])

        AsyncLoop.update(sum([node.tasks for node in self.nodes], []))
        AsyncLoop.update(self.tasks)

        await AsyncLoop.gather()

    def stop(self):
        """
        Stop the node.
        """
        logger.info("CTCore stopped")
        self.running = False

        for node in self.nodes:
            for s in node.session_management.values():
                s.socket.close()
