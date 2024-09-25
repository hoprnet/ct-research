# region Imports
import asyncio
import random

from prometheus_client import Gauge

from .components import AsyncLoop, Base, HoprdAPI, LockedVar, Parameters, Utils
from .components.decorators import flagguard, formalin
from .model import Address, Peer
from .model.economic_model import EconomicModelLegacy, EconomicModelSigmoid
from .model.subgraph import (
    AllocationEntry,
    AllocationsProvider,
    BalanceEntry,
    EOABalanceProvider,
    FundingsProvider,
    GraphQLProvider,
    NodeEntry,
    ProviderError,
    RewardsProvider,
    SafesProvider,
    StakingProvider,
    SubgraphURL,
    TopologyEntry,
)
from .node import Node

# endregion

# region Metrics
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")
ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", ["peer_id", "model"]
)
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")
# endregion


class Core(Base):
    """
    The Core class represents the main class of the application. It is responsible for managing the nodes, the economic model and the distribution of rewards.
    """

    def __init__(self, nodes: list[Node], params: Parameters):
        super().__init__()

        self.params = params
        self.nodes = nodes
        for node in self.nodes:
            node.params = params

        self.models = {
            "legacy": EconomicModelLegacy.fromParameters(
                self.params.economicModel.legacy
            ),
            "sigmoid": EconomicModelSigmoid.fromParameters(
                self.params.economicModel.sigmoid
            ),
        }

        self.tasks = set[asyncio.Task]()

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_data = list[TopologyEntry]()
        self.registered_nodes_data = list[NodeEntry]()
        self.nft_holders_data = list[str]()
        self.allocations_data = list[AllocationEntry]()
        self.eoa_balances_data = list[BalanceEntry]()
        self.peers_rewards_data = dict[str, float]()

        self.subgraph_providers: dict[str, GraphQLProvider] = {
            "safes": SafesProvider(SubgraphURL(self.params.subgraph, "safesBalance")),
            "staking": StakingProvider(SubgraphURL(self.params.subgraph, "staking")),
            "rewards": RewardsProvider(SubgraphURL(self.params.subgraph, "rewards")),
            "mainnet_allocations": AllocationsProvider(
                SubgraphURL(self.params.subgraph, "mainnetAllocations")
            ),
            "gnosis_allocations": AllocationsProvider(
                SubgraphURL(self.params.subgraph, "gnosisAllocations")
            ),
            "mainnet_balances": EOABalanceProvider(
                SubgraphURL(self.params.subgraph, "hoprOnMainet")
            ),
            "gnosis_balances": EOABalanceProvider(
                SubgraphURL(self.params.subgraph, "hoprOnGnosis")
            ),
            "fundings": FundingsProvider(SubgraphURL(self.params.subgraph, "fundings")),
        }

        self.running = False

    @property
    def api(self) -> HoprdAPI:
        return random.choice(self.nodes).api

    @property
    def channels(self):
        return random.choice(self.nodes).channels

    @property
    def ct_nodes_addresses(self) -> list[Address]:
        return [node.address for node in self.nodes]

    @flagguard
    @formalin
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph type in use (default, backup or none).
        """
        for provider in self.subgraph_providers.values():
            await provider.test(self.params.subgraph.type)

    @flagguard
    @formalin
    async def connected_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """

        counts = {"new": 0, "known": 0, "unreachable": 0}

        # TODO: does this work ?
        async with self.all_peers as current_peers:
            visible_peers: set[Peer] = set()
            visible_peers.update(*[await node.peers.get() for node in self.nodes])

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

            self.debug(
                f"Aggregated peers ({len(current_peers)} entries) ({', '.join([f'{value} {key}' for key, value in counts.items() ] )})."
            )
            for key, value in counts.items():
                UNIQUE_PEERS.labels(key).set(value)

    @flagguard
    @formalin
    async def registered_nodes(self):
        """
        Gets all registered nodes in the Network Registry.
        """

        results = list[NodeEntry]()
        try:
            for safe in await self.subgraph_providers["safes"].get():
                entries = [
                    NodeEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
                results.extend(entries)

        except ProviderError as err:
            self.error(f"get_registered_nodes: {err}")

        self.registered_nodes_data = results
        SUBGRAPH_SIZE.set(len(results))
        self.debug(f"Fetched registered nodes ({len(results)} entries).")

    @flagguard
    @formalin
    async def nft_holders(self):
        """
        Gets all NFT holders.
        """
        results = list[str]()
        try:
            for nft in await self.subgraph_providers["staking"].get():
                if owner := nft.get("owner", {}).get("id", None):
                    results.append(owner)

        except ProviderError as err:
            self.error(f"nft_holders: {err}")

        self.nft_holders_data = results
        NFT_HOLDERS.set(len(results))
        self.debug(f"Fetched NFT holders ({len(results)} entries).")

    @flagguard
    @formalin
    async def allocations(self):
        """
        Gets all allocations for the investors.
        The amount per investor is then added to their stake before dividing it by the number of nodes they are running.
        """
        results = list[AllocationEntry]()
        try:
            for account in await self.subgraph_providers["mainnet_allocations"].get():
                results.append(AllocationEntry(**account["account"]))
        except ProviderError as err:
            self.error(f"allocations: {err}")

        try:
            for account in await self.subgraph_providers["gnosis_allocations"].get():
                results.append(AllocationEntry(**account["account"]))
        except ProviderError as err:
            self.error(f"allocations: {err}")

        self.allocations_data = results
        self.debug(f"Fetched allocations ({len(results)} entries).")

    @flagguard
    @formalin
    async def eoa_balances(self):
        """
        Gets the EOA balances on Gnosis and Mainnet for the investors.
        """
        balances = {alloc.address: 0 for alloc in self.allocations_data}
        if len(balances) == 0:
            self.info("No investors addresses found.")
            return

        try:
            for account in await self.subgraph_providers["mainnet_balances"].get(
                id_in=list(balances.keys())
            ):
                balances[account["id"]] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        try:
            for account in await self.subgraph_providers["gnosis_balances"].get(
                id_in=list(balances.keys())
            ):
                balances[account["id"]] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        self.eoa_balances_data = [
            BalanceEntry(key, value) for key, value in balances.items()
        ]
        self.debug(f"Fetched EOA balances ({len(balances)} entries).")

    @flagguard
    @formalin
    async def topology(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """

        if self.channels is None:
            self.warning("Topology data not available")
            return

        self.topology_data = [
            TopologyEntry.fromDict(*arg)
            for arg in (
                await Utils.balanceInChannels(
                    self.channels.outgoing + self.channels.incoming
                )
            ).items()
        ]

        TOPOLOGY_SIZE.set(len(self.topology_data))
        self.debug(f"Fetched topology links ({len(self.topology_data)} entries).")

    @flagguard
    @formalin
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        async with self.all_peers as peers:
            if not all(
                [len(self.topology_data), len(self.registered_nodes_data), len(peers)]
            ):
                self.warning("Not enough data to apply economic model.")
                return

            Utils.associateEntitiesToNodes(
                self.allocations_data, self.registered_nodes_data
            )
            Utils.associateEntitiesToNodes(
                self.eoa_balances_data, self.registered_nodes_data
            )

            await Utils.mergeDataSources(
                self.topology_data,
                peers,
                self.registered_nodes_data,
                self.allocations_data,
                self.eoa_balances_data,
            )

            for p in peers:
                if p.is_old(self.params.peer.minVersion):
                    p.yearly_message_count = None

            Utils.allowManyNodePerSafe(peers)

            for p in peers:
                if not p.is_eligible(
                    self.params.economicModel.minSafeAllowance,
                    self.legacy_model.coefficients.l,
                    self.ct_nodes_addresses,
                    self.nft_holders_data,
                    self.params.economicModel.NFTThreshold,
                ):
                    p.yearly_message_count = None

            economic_security = (
                sum(
                    [p.split_stake for p in peers if p.yearly_message_count is not None]
                )
                / self.params.economicModel.sigmoid.totalTokenSupply
            )
            network_capacity = (
                len([p for p in peers if p.yearly_message_count is not None])
                / self.params.economicModel.sigmoid.networkCapacity
            )
            sigmoid_model_input = [economic_security, network_capacity]

            for peer in peers:
                if peer.yearly_message_count is None:
                    continue

                legacy_message_count = self.models["legacy"].yearly_message_count(
                    peer.split_stake,
                    self.peers_rewards_data.get(peer.address.address, 0.0),
                )
                sigmoid_message_count = self.models["sigmoid"].yearly_message_count(
                    peer.split_stake, sigmoid_model_input
                )

                peer.yearly_message_count = legacy_message_count + sigmoid_message_count

                MESSAGE_COUNT.labels(peer.address.id, "legacy").set(
                    legacy_message_count
                )
                MESSAGE_COUNT.labels(peer.address.id, "sigmoid").set(
                    sigmoid_message_count
                )

            eligibles = sum([p.yearly_message_count is not None for p in peers])
            self.info(f"Eligible nodes: {eligibles} entries.")
            ELIGIBLE_PEERS.set(eligibles)

    @flagguard
    @formalin
    async def peers_rewards(self):
        results = dict()
        try:
            for account in await self.subgraph_providers["rewards"].get():
                results[account["id"]] = float(account["redeemedValue"])

        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")

        self.peers_rewards_data = results
        self.debug(f"Fetched peers rewards amounts ({len(results)} entries).")

    @flagguard
    @formalin
    async def ticket_parameters(self):
        """
        Gets the ticket price and winning probability from the api. They are used in the economic model to calculate the number of messages to send to a peer.
        """
        price = await self.api.ticket_price()
        if price is None:
            self.warning("Ticket price not available.")
            return

        # should be replaced by await self.api.winning_probability()
        win_probabilty = self.params.economicModel.winningProbability
        if win_probabilty is None:
            self.warning("Winning probability not available.")
            return

        self.debug(f"Ticket price: {price}, winning probability: {win_probabilty}")

        for model in self.models.values():
            model.budget.ticket_price = price
            model.budget.winning_probability = win_probabilty

    @flagguard
    @formalin
    async def safe_fundings(self):
        """
        Gets the total amount that was sent to CT safes.
        """
        provider = self.subgraph_providers["fundings"]

        addresses = list(
            set([(await node.api.node_info()).hopr_node_safe for node in self.nodes])
        )
        try:
            entries = await provider.get(to_in=addresses)
        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")
            entries = []
        amount = sum([float(item["amount"]) for item in entries])

        TOTAL_FUNDING.set(amount + self.params.fundings.constant)
        self.debug(f"Safe fundings: {amount} + {self.params.fundings.constant}")

    async def start(self):
        """
        Start the node.
        """
        self.info(f"CTCore started with {len(self.nodes)} nodes.")

        if AsyncLoop.hasRunningTasks():
            return

        for node in self.nodes:
            node.running = True
            await node._healthcheck()
            AsyncLoop.update(await node.tasks())

        self.running = True

        AsyncLoop.update(
            [
                self.rotate_subgraphs,
                self.peers_rewards,
                self.ticket_parameters,
                self.connected_peers,
                self.registered_nodes,
                self.topology,
                self.nft_holders,
                self.allocations,
                self.eoa_balances,
                self.apply_economic_model,
                self.safe_fundings,
            ]
        )

        for node in self.nodes:
            AsyncLoop.add(node.watch_message_queue)

        await AsyncLoop.gather()
