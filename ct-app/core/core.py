# region Imports
import asyncio
import random

from prometheus_client import Gauge

from .components import AsyncLoop, Base, HoprdAPI, LockedVar, Parameters, Utils
from .components.decorators import connectguard, flagguard, formalin
from .components.graphql_providers import (
    ProviderError,
    RewardsProvider,
    SafesProvider,
    StakingProvider,
)
from .model import Address, NodeSafeEntry, Peer, TopologyEntry
from .model.economic_model import EconomicModelLegacy, EconomicModelSigmoid
from .model.subgraph import SubgraphType, SubgraphURL
from .node import Node

# endregion

# region Metrics
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers")
SUBGRAPH_IN_USE = Gauge("ct_subgraph_in_use", "Subgraph in use")
SUBGRAPH_CALLS = Gauge("ct_subgraph_calls", "# of subgraph calls", ["type"])
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

        self.legacy_model = EconomicModelLegacy.fromParameters(
            self.params.economicModel.legacy
        )
        self.sigmoid_model = EconomicModelSigmoid.fromParameters(
            self.params.economicModel.sigmoid
        )

        self.legacy_model: EconomicModelLegacy = None
        self.sigmoid_model: EconomicModelSigmoid = None
        self._budget: Budget = None

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.registered_nodes_list = LockedVar("subgraph_list", list[NodeSafeEntry]())
        self.nft_holders_list = LockedVar("nft_holders", list[str]())
        self.peer_rewards = LockedVar("peer_rewards", dict[str, float]())

        self.subgraph_type = SubgraphType.DEFAULT

        self.running = False

    @property
    def api(self) -> HoprdAPI:
        return random.choice(self.nodes).api

    @property
    async def ct_nodes_addresses(self) -> list[Address]:
        return await asyncio.gather(*[node.address.get() for node in self.nodes])

    @property
    def subgraph_type(self) -> SubgraphType:
        return self._subgraph_type

    @subgraph_type.setter
    def subgraph_type(self, value: SubgraphType):
        if not hasattr(self, "_subgraph_type") or value != self._subgraph_type:
            self.info(f"Now using '{value.value}' subgraph.")

        subgraph_params = self.params.subgraph
        key = subgraph_params.apiKey

        self.safe_subgraph_url = SubgraphURL(key, subgraph_params.safesBalance)(value)
        self.staking_subgraph_url = SubgraphURL(key, subgraph_params.staking)(value)
        self.rewards_subgraph_url = SubgraphURL(key, subgraph_params.rewards)(value)

        SUBGRAPH_IN_USE.set(value.toInt())
        self._subgraph_type = value

    @flagguard
    @formalin(None)
    async def healthcheck(self) -> dict:
        """
        Checks the health of the node. Sets the connected status (LockedVar) and the Prometheus metric accordingly.
        """
        health = await self.api.healthyz()

        await self.connected.set(health)

    @flagguard
    @formalin("Checking subgraph URLs")
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph type in use (default, backup or none)
        """
        for type in SubgraphType.callables():
            self.subgraph_type = type
            if await SafesProvider(self.safe_subgraph_url).test():
                break
        else:
            self.subgraph_type = SubgraphType.NONE

        SUBGRAPH_CALLS.labels(type.value).inc()

    @flagguard
    @formalin("Aggregating peers")
    async def connected_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """
        visible_peers = set[Peer]()

        known_peers: set[Peer] = await self.all_peers.get()

        for node in self.nodes:
            visible_peers.update(await node.peers.get())

        # set yearly message count to None (-> not eligible for rewards) for peers that are not visible anymore
        for peer in known_peers - visible_peers:
            await peer.yearly_message_count.set(None)

        # add new peers to the set
        for peer in visible_peers - known_peers:
            peer.params = self.params
            peer.running = True
            known_peers.add(peer)

        await self.all_peers.set(known_peers)

        self.debug(f"Aggregated peers ({len(known_peers)} entries).")
        UNIQUE_PEERS.set(len(known_peers))

    @flagguard
    @formalin("Getting registered nodes")
    async def registered_nodes(self):
        """
        Gets the subgraph data and sets the subgraph_list LockedVar.
        """
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = SafesProvider(self.safe_subgraph_url)
        results = list[NodeSafeEntry]()
        try:
            for safe in await provider.get():
                entries = [
                    NodeSafeEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
                results.extend(entries)

        except ProviderError as err:
            self.error(f"get_registered_nodes: {err}")

        await self.registered_nodes_list.set(results)

        SUBGRAPH_SIZE.set(len(results))
        self.debug(f"Fetched registered nodes ({len(results)} entries).")

    @flagguard
    @formalin("Getting NFT holders")
    async def nft_holders(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = StakingProvider(self.staking_subgraph_url)

        results = list[str]()
        try:
            for nft in await provider.get():
                if owner := nft.get("owner", {}).get("id", None):
                    results.append(owner)

        except ProviderError as err:
            self.error(f"get_nft_holders: {err}")

        await self.nft_holders_list.set(results)

        NFT_HOLDERS.set(len(results))
        self.debug(f"Fetched NFT holders ({len(results)} entries).")

    @flagguard
    @formalin("Getting topology data")
    @connectguard
    async def topology(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        channels = await self.api.all_channels(False)

        if channels is None:
            self.warning("Topology data not available")
            return

        results = await Utils.balanceInChannels(channels.all)
        topology_list = [TopologyEntry.fromDict(*arg) for arg in results.items()]

        await self.topology_list.set(topology_list)

        TOPOLOGY_SIZE.set(len(topology_list))
        self.debug(f"Fetched topology links ({len(topology_list)} entries).")

    @flagguard
    @formalin("Applying economic model")
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        registered_nodes = await self.registered_nodes_list.get()
        nft_holders = await self.nft_holders_list.get()
        topology = await self.topology_list.get()
        peers = await self.all_peers.get()
        ct_nodes = await self.ct_nodes_addresses
        redeemed_rewards = await self.peer_rewards.get()

        if not all(
            [len(topology), len(registered_nodes), len(peers), len(nft_holders)]
        ):
            self.warning("Not enough data to apply economic model.")
            return

        eligibles = Utils.mergeDataSources(topology, peers, registered_nodes)
        self.info(f"Merged topology and subgraph data ({len(eligibles)} entries).")

        old_peer_addresses = [
            peer.address
            for peer in eligibles
            if peer.version_is_old(self.params.peer.minVersion)
        ]
        excluded = Utils.exclude(eligibles, old_peer_addresses)
        self.info(
            f"Excluded peers running on old version (< {self.params.peer.minVersion}) ({len(excluded)} entries)."
        )

        Utils.allowManyNodePerSafe(eligibles)
        self.debug(f"Allowed many nodes per safe ({len(eligibles)} entries).")

        low_allowance_addresses = [
            peer.address
            for peer in eligibles
            if peer.safe_allowance < self.params.economicModel.minSafeAllowance
        ]
        excluded = Utils.exclude(eligibles, low_allowance_addresses)
        self.info(f"Excluded nodes with low safe allowance ({len(excluded)} entries).")
        self.debug(f"Peers with low allowance {[el.address.id for el in excluded]}")

        excluded = Utils.exclude(eligibles, await self.network_nodes_addresses)
        self.debug(f"Excluded network nodes ({len(excluded)} entries).")

        if threshold := self.params.economicModel.NFTThreshold:
            low_stake_non_nft_holders = [
                peer.address
                for peer in eligibles
                if peer.safe_address not in nft_holders and peer.split_stake < threshold
            ]
            excluded = Utils.exclude(eligibles, low_stake_non_nft_holders)
            self.info(
                f"Excluded non-nft-holders with stake < {threshold} ({len(excluded)} entries)."
            )

        redeemed_rewards = await self.peer_rewards.get()
        for peer in eligibles:
            peer.economic_model = deepcopy(self.legacy_model)
            peer.economic_model.coefficients.c += redeemed_rewards.get(
                peer.address.address, 0.0
            )

        low_stake_addresses = [peer.address for peer in eligibles if peer.has_low_stake]
        excluded = Utils.exclude(eligibles, low_stake_addresses)
        self.debug(f"Excluded nodes with low stake ({len(excluded)} entries).")

        economic_security = (
            sum([peer.split_stake for peer in eligibles])
            / self.params.economicModel.sigmoid.totalTokenSupply
        )
        network_capacity = (
            len(eligibles) / self.params.economicModel.sigmoid.networkCapacity
        )

        for peer in eligibles:
            legacy_message_count = self.legacy_model.message_count_for_reward(
                peer.split_stake
            )
            sigmoid_message_count = self.sigmoid_model.message_count_for_reward(
                peer.split_stake, [economic_security, network_capacity]
            )

            peer.message_count = legacy_message_count + sigmoid_message_count
            JOBS_PER_PEER.labels(peer.address.id, "legacy").set(legacy_message_count)
            JOBS_PER_PEER.labels(peer.address.id, "sigmoid").set(sigmoid_message_count)

        self.info(
            f"Assigned economic model to eligible nodes. ({len(eligibles)} entries)."
        )

        self.info(f"Eligible nodes ({len(eligibles)} entries).")

        await self.eligible_list.set(eligibles)

        # set prometheus metrics
        NEXT_DISTRIBUTION_EPOCH.set(
            Utils.nextEpoch(self.params.economicModel.intervals).timestamp()
        )
        ELIGIBLE_PEERS_COUNTER.set(len(eligibles))

        for peer in eligibles:
            PEER_SPLIT_STAKE.labels(peer.address.id).set(peer.split_stake)
            PEER_SAFE_COUNT.labels(peer.address.id).set(peer.safe_address_count)
            PEER_TF_STAKE.labels(peer.address.id).set(peer.transformed_stake)
            PEER_VERSION.labels(peer.address.id, str(peer.version)).set(1)


    @flagguard
    @formalin("Getting peers rewards amounts")
    async def peers_rewards(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = RewardsProvider(self.rewards_subgraph_url)

        results = dict()
        try:
            for account in await provider.get():
                results[account["id"]] = float(account["redeemedValue"])

        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")

        await self.peer_rewards.set(results)

        self.debug(f"Fetched peers rewards amounts ({len(results)} entries).")

    @flagguard
    @formalin("Getting ticket parameters")
    @connectguard
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

        self.legacy_model.budget.ticket_price = price
        self.legacy_model.budget.winning_probability = win_probabilty
        self.sigmoid_model.budget.ticket_price = price
        self.sigmoid_model.budget.winning_probability = win_probabilty

    async def start(self):
        """
        Start the node.
        """
        self.info(f"CTCore started with {len(self.nodes)} nodes.")

        if AsyncLoop.hasRunningTasks():
            return

        for node in self.nodes:
            node.running = True
            AsyncLoop.update(await node.tasks())

        self.running = True

        AsyncLoop.update(
            [
                self.healthcheck,
                self.rotate_subgraphs,
                self.peers_rewards,
                self.ticket_parameters,
                self.connected_peers,
                self.registered_nodes,
                self.topology,
                self.nft_holders,
                self.apply_economic_model,
            ]
        )

        for node in self.nodes:
            AsyncLoop.add(node.watch_message_queue)

        await AsyncLoop.gather()
