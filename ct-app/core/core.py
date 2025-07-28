# region Imports
import logging
import random

from prometheus_client import Gauge

from .api import HoprdAPI
from .components import Address, AsyncLoop, LockedVar, Parameters, Peer, Utils
from .components.decorators import flagguard, formalin, master
from .components.logs import configure_logging
from .economic_model import EconomicModelTypes
from .node import Node
from .rpc import entries as rpc_entries
from .rpc.providers import (
    GnosisDistributor,
    HOPRBalance,
    MainnetDistributor,
    wxHOPRBalance,
    xHOPRBalance,
)
from .subgraph import URL, GraphQLProvider
from .subgraph import Type as SubgraphType
from .subgraph import entries as subgraph_entries

# endregion

# region Metrics
BALANCE_MULTIPLIER = Gauge("ct_balance_multiplier", "factor to multiply the balance by")
ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["peer_id", "model"]
)
NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")
PEER_VERSION = Gauge("ct_peer_version", "Peer version", ["peer_id", "version"])
REDEEMED_REWARDS = Gauge("ct_redeemed_rewards", "Redeemed rewards", ["address"])
STAKE = Gauge("ct_peer_stake", "Stake", ["safe", "type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
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
        self.topology_data = list[subgraph_entries.Topology]()
        self.registered_nodes_data = list[subgraph_entries.Node]()
        self.nft_holders_data = list[str]()
        self.allocations_data = list[rpc_entries.Allocation]()
        self.eoa_balances_data = list[rpc_entries.ExternalBalance]()
        self.peers_rewards_data = dict[str, float]()

        self.models = {
            m: m.model.fromParameters(getattr(self.params.economicModel, m.value))
            for m in EconomicModelTypes
        }

        self.graphql_providers: dict[SubgraphType, GraphQLProvider] = {
            s: s.provider(URL(self.params.subgraph, s.value)) for s in SubgraphType
        }

        self.running = True

        BALANCE_MULTIPLIER.set(1e18)

    @property
    def api(self) -> HoprdAPI:
        return random.choice(self.nodes).api

    @property
    def channels(self):
        return random.choice(self.nodes).channels

    @property
    def ct_nodes_addresses(self) -> list[Address]:
        return [node.address for node in self.nodes]

    @master(flagguard, formalin)
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph mode in use (default, backup or none).
        """
        logger.info("Rotating subgraphs")
        for provider in self.graphql_providers.values():
            await provider.test(self.params.subgraph.type)

    @master(flagguard, formalin)
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

                    # update peer version if it has been succesfully retrieved
                    new_version = visible_peers[visible_peers.index(peer)].version
                    if new_version.major != 0:
                        peer.version = new_version

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

            for peer in current_peers:
                PEER_VERSION.labels(peer.address.hopr, str(peer.version)).set(1)

    @master(flagguard, formalin)
    async def registered_nodes(self):
        """
        Gets all registered nodes in the Network Registry.
        """

        results = list[subgraph_entries.Node]()
        for safe in await self.graphql_providers[SubgraphType.SAFES].get():
            results.extend(
                [
                    subgraph_entries.Node.fromSubgraphResult(node)
                    for node in safe["registeredNodesInSafeRegistry"]
                ]
            )

        for node in results:
            STAKE.labels(node.safe.address, "balance").set(node.safe.balance)
            STAKE.labels(node.safe.address, "allowance").set(node.safe.allowance)
            STAKE.labels(node.safe.address, "additional_balance").set(node.safe.additional_balance)

        self.registered_nodes_data = results
        logger.debug("Fetched registered nodes in the safe registry", {"count": len(results)})
        SUBGRAPH_SIZE.set(len(results))

    @formalin
    async def allocations(self):
        """
        Gets all allocations for the investors.
        The amount per investor is then added to their stake before dividing it by the number
        of nodes they are running.
        """
        addresses: list[str] = self.params.investors.addresses
        schedule: str = self.params.investors.schedule

        gno_query_provider = GnosisDistributor(self.params.rpc.gnosis)
        eth_query_provider = MainnetDistributor(self.params.rpc.mainnet)

        futures = []
        futures.extend(
            [gno_query_provider.allocations(addr, schedule) for addr in addresses]
        )
        futures.extend(
            [eth_query_provider.allocations(addr, schedule) for addr in addresses]
        )

        self.allocations_data = await AsyncLoop.gather_any(futures)

        logger.debug(
            "Fetched investors allocations", {"counts": len(self.allocations_data)}
        )

    @master(flagguard, formalin)
    async def eoa_balances(self):
        """
        Gets the EOA balances on Gnosis and Mainnet for the investors.
        """
        addresses: list[str] = self.params.investors.addresses

        hopr_contract_provider = HOPRBalance(self.params.rpc.mainnet)
        xhopr_contract_provider = xHOPRBalance(self.params.rpc.gnosis)
        wxhopr_contract_provider = wxHOPRBalance(self.params.rpc.gnosis)

        futures = []
        futures.extend([hopr_contract_provider.balance_of(addr) for addr in addresses])
        futures.extend([xhopr_contract_provider.balance_of(addr) for addr in addresses])
        futures.extend(
            [wxhopr_contract_provider.balance_of(addr) for addr in addresses]
        )

        self.eoa_balances_data = await AsyncLoop.gather_any(futures)

        logger.debug(
            "Fetched investors EOA balances", {"count": len(self.eoa_balances_data)}
        )

    @master(flagguard, formalin)
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
            subgraph_entries.Topology.fromDict(*arg)
            for arg in (await Utils.balanceInChannels(channels.all)).items()
        ]

        logger.debug("Fetched all topology links", {"count": len(self.topology_data)})
        TOPOLOGY_SIZE.set(len(self.topology_data))

    @master(flagguard, formalin)
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        async with self.all_peers as peers:
            if not all([len(self.topology_data), len(self.registered_nodes_data), len(peers)]):
                logger.warning("Not enough data to apply economic model")
                return

            Utils.associateEntitiesToNodes(self.allocations_data, self.registered_nodes_data)
            Utils.associateEntitiesToNodes(self.eoa_balances_data, self.registered_nodes_data)

            await Utils.mergeDataSources(
                self.topology_data,
                peers,
                self.registered_nodes_data,
                self.allocations_data,
                self.eoa_balances_data,
            )

            Utils.allowManyNodePerSafe(peers)

            for p in peers:
                if not p.is_eligible(
                    self.params.economicModel.minSafeAllowance,
                    self.models[EconomicModelTypes.LEGACY].coefficients.l,
                    self.ct_nodes_addresses,
                    self.nft_holders_data,
                    self.params.economicModel.NFTThreshold,
                ):
                    p.yearly_message_count = None

            economic_security = (
                sum([p.split_stake for p in peers if p.yearly_message_count is not None])
                / self.params.economicModel.sigmoid.totalTokenSupply
            )
            network_capacity = (
                len([p for p in peers if p.yearly_message_count is not None])
                / self.params.economicModel.sigmoid.networkCapacity
            )

            model_input = {
                EconomicModelTypes.LEGACY: 0,
                EconomicModelTypes.SIGMOID: [economic_security, network_capacity],
            }
            message_count = {
                EconomicModelTypes.LEGACY: 0,
                EconomicModelTypes.SIGMOID: 0,
            }
            for peer in peers:
                if peer.yearly_message_count is None:
                    continue

                model_input[EconomicModelTypes.LEGACY] = self.peers_rewards_data.get(
                    peer.address.native, 0.0
                )

                for model in self.models:
                    message_count[model] = self.models[model].yearly_message_count(
                        peer.split_stake,
                        model_input[model],
                    )

                    MESSAGE_COUNT.labels(peer.address.hopr, model.name).set(message_count[model])

                peer.yearly_message_count = sum(message_count.values())

            eligible_count = sum([p.yearly_message_count is not None for p in peers])
            logger.info("Generated the eligible nodes set", {"count": eligible_count})
            ELIGIBLE_PEERS.set(eligible_count)

    @master(flagguard, formalin)
    async def peers_rewards(self):
        results = dict()
        for acc in await self.graphql_providers[SubgraphType.REWARDS].get():
            account = subgraph_entries.Account.fromSubgraphResult(acc)
            results[account.address] = account.redeemed_value
            REDEEMED_REWARDS.labels(account.address).set(account.redeemed_value)

        self.peers_rewards_data = results
        logger.debug("Fetched peers rewards amounts", {"count": len(results)})

    @master(flagguard, formalin)
    async def ticket_parameters(self):
        """
        Gets the ticket price from the api.
        They are used in the economic model to calculate the number of messages to send to a peer.
        """
        ticket_price = await self.api.ticket_price()
        logger.debug("Fetched ticket price", {"value": getattr(ticket_price, "value", None)})

        if ticket_price is not None:
            for model in self.models.values():
                model.budget.ticket_price = ticket_price.value

    async def get_nft_holders(self):
        """
        Gets all NFT holders.
        """
        with open(self.params.nftHolders.filepath, "r") as f:
            data: list[str] = [line.strip() for line in f if line.strip()]

        if len(data) == 0:
            logger.warning("No NFT holders data found")

        self.nft_holders_data: list[str] = data

        logger.debug("Fetched NFT holders", {"count": len(self.nft_holders_data)})
        NFT_HOLDERS.set(len(self.nft_holders_data))

    @master(flagguard, formalin)
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
            await node.open_sessions(eligible_addresses)

    @property
    def tasks(self):
        return [getattr(self, method) for method in Utils.decorated_methods(__file__, "formalin")]

    async def start(self):
        """
        Start the node.
        """
        logger.info("CTCore started", {"num_nodes": len(self.nodes)})

        await AsyncLoop.gather_any([node._healthcheck() for node in self.nodes])
        await AsyncLoop.gather_any([node.close_all_sessions() for node in self.nodes])

        await AsyncLoop.gather_any([self.get_nft_holders()])

        self.running = True

        AsyncLoop.update(
            set(
                [
                    self.rotate_subgraphs,
                    self.peers_rewards,
                    self.ticket_parameters,
                    self.connected_peers,
                    self.registered_nodes,
                    self.topology,
                    self.allocations,
                    self.eoa_balances,
                    self.apply_economic_model,
                ]
            )
        )

        for node in self.nodes:
            AsyncLoop.add(node.observe_message_queue)

        await AsyncLoop.gather()

    def stop(self):
        """
        Stop the node.
        """
        logger.info("CTCore stopped")
        self.running = False
        self.running = False
