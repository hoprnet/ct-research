import asyncio
import random

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.decorators import connectguard, flagguard, formalin
from .components.graphql_providers import (
    ProviderError,
    RewardsProvider,
    SafesProvider,
    StakingProvider,
)
from .components.hoprd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.economic_model_legacy import EconomicModelLegacy
from .model.economic_model_sigmoid import EconomicModelSigmoid
from .model.peer import Peer
from .model.subgraph_entry import SubgraphEntry
from .model.subgraph_type import SubgraphType
from .model.subgraph_url import SubgraphURL
from .model.topology_entry import TopologyEntry
from .node import Node

HEALTH = Gauge("core_health", "Node health")
UNIQUE_PEERS = Gauge("unique_peers", "Unique peers")
SUBGRAPH_IN_USE = Gauge("subgraph_in_use", "Subgraph in use")
SUBGRAPH_CALLS = Gauge("subgraph_calls", "# of subgraph calls", ["type"])
SUBGRAPH_SIZE = Gauge("subgraph_size", "Size of the subgraph")
TOPOLOGY_SIZE = Gauge("topology_size", "Size of the topology")
NFT_HOLDERS = Gauge("nft_holders", "Number of nr-nft holders")
ELIGIBLE_PEERS_COUNTER = Gauge("eligible_peers", "# of eligible peers for rewards")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")


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

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.registered_nodes = LockedVar("subgraph_list", list[SubgraphEntry]())
        self.nft_holders = LockedVar("nft_holders", list[str]())
        self.peer_rewards = LockedVar("peer_rewards", dict[str, float]())

        self.subgraph_type = SubgraphType.DEFAULT

        self.started = False

    @property
    def print_prefix(self) -> str:
        return "ct-core"

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

        self.debug(f"Connection state: {health}")
        HEALTH.set(int(health))

    @flagguard
    @formalin("Checking subgraph URLs")
    async def check_subgraph_urls(self):
        """
        Checks the subgraph URLs and sets the subgraph type in use (default, backup or none)
        """
        for type in SubgraphType.callables():
            self.subgraph_type = type
            provider = SafesProvider(self.safe_subgraph_url)

            if not await provider.test():
                continue
            else:
                break
        else:
            self.subgraph_type = SubgraphType.NONE

        SUBGRAPH_CALLS.labels(type.value).inc()

    @flagguard
    @formalin("Aggregating peers")
    async def aggregate_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """
        visible_peers = set[Peer]()
        previous_peers: set[Peer] = await self.all_peers.get()

        for node in self.nodes:
            visible_peers.update(await node.peers.get())

        for peer in previous_peers:
            if peer in visible_peers:
                continue
            await peer.message_count.set(None)

        for peer in visible_peers:
            if peer in previous_peers:
                continue
            previous_peers.add(peer)

        await self.all_peers.set(previous_peers)

        self.debug(f"Aggregated peers ({len(previous_peers)} entries).")
        UNIQUE_PEERS.set(len(previous_peers))

    @flagguard
    @formalin("Getting registered nodes")
    async def get_registered_nodes(self):
        """
        Gets the subgraph data and sets the subgraph_list LockedVar.
        """
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = SafesProvider(self.safe_subgraph_url)
        results = list[SubgraphEntry]()
        try:
            for safe in await provider.get():
                entries = [
                    SubgraphEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
                results.extend(entries)

        except ProviderError as err:
            self.error(f"get_registered_nodes: {err}")

        await self.registered_nodes.set(results)

        SUBGRAPH_SIZE.set(len(results))
        self.debug(f"Fetched subgraph data ({len(results)} entries).")

    @flagguard
    @formalin("Getting NFT holders")
    async def get_nft_holders(self):
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

        await self.nft_holders.set(results)

        NFT_HOLDERS.set(len(results))
        self.debug(f"Fetched NFT holders ({len(results)} entries).")

    @flagguard
    @formalin("Getting topology data")
    @connectguard
    async def get_topology_data(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        channels = await self.api.all_channels(False)

        if channels is None:
            self.warning("Topology data not available")
            return

        results = await Utils.aggregatePeerBalanceInChannels(channels.all)
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
        registered_nodes = await self.registered_nodes.get()
        nft_holders = await self.nft_holders.get()
        topology = await self.topology_list.get()
        peers = await self.all_peers.get()

        if not all(
            [len(topology), len(registered_nodes), len(peers), len(nft_holders)]
        ):
            self.warning("Not enough data to apply economic model.")
            return

        peers = await Utils.mergeDataSources(topology, peers, registered_nodes)

        for p in peers:
            if not p.is_old(self.params.peer.minVersion):
                continue
            await p.message_count.set(None)

        Utils.allowManyNodePerSafe(peers)

        ct_nodes = await self.ct_nodes_addresses
        for p in peers:
            if not p.is_eligible(
                self.params.economicModel.minSafeAllowance,
                self.legacy_model.coefficients.l,
                ct_nodes,
                nft_holders,
                self.params.economicModel.NFTThreshold,
            ):
                continue
            await p.message_count.set(None)

        economic_security = (
            sum([peer.split_stake for peer in peers])
            / self.params.economicModel.sigmoid.totalTokenSupply
        )
        network_capacity = (
            len([p for p in peers if p.message_count is not None])
            / self.params.economicModel.sigmoid.networkCapacity
        )
        sigmoid_model_input = [economic_security, network_capacity]
        redeemed_rewards = await self.peer_rewards.get()

        for peer in peers:
            legacy_message_count = self.legacy_model.message_count_for_reward(
                peer.split_stake, redeemed_rewards.get(peer.address.address, 0.0)
            )
            sigmoid_message_count = self.sigmoid_model.message_count_for_reward(
                peer.split_stake, sigmoid_model_input
            )

            await peer.message_count.set(legacy_message_count + sigmoid_message_count)

        self.info(
            f"Eligible nodes: {len([p for p in peers if p.message_count is not None])} entries."
        )

        ELIGIBLE_PEERS_COUNTER.set(len(peers))
        await self.all_peers.set(set(peers))

    @flagguard
    @formalin("Getting peers rewards amounts")
    async def get_peers_rewards(self):
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

    @formalin("Getting ticket parameters")
    @connectguard
    async def get_ticket_parameters(self):
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

        if len(self.nodes) == 0:
            self.error("No nodes available, exiting.")
            return

        if self.tasks:
            return

        for node in self.nodes:
            node.started = True
            await node.retrieve_address()
            self.tasks.update(node.tasks())

        self.started = True

        self.tasks.add(asyncio.create_task(self.healthcheck()))
        self.tasks.add(asyncio.create_task(self.check_subgraph_urls()))
        self.tasks.add(asyncio.create_task(self.get_peers_rewards()))
        self.tasks.add(asyncio.create_task(self.get_ticket_parameters()))

        self.tasks.add(asyncio.create_task(self.aggregate_peers()))
        self.tasks.add(asyncio.create_task(self.get_registered_nodes()))
        self.tasks.add(asyncio.create_task(self.get_topology_data()))
        self.tasks.add(asyncio.create_task(self.get_nft_holders()))

        self.tasks.add(asyncio.create_task(self.apply_economic_model()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stop the node.
        """
        self.started = False

        for node in self.nodes:
            node.started = False

        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()
            task.add_done_callback(self.tasks.discard)
            task.cancel()
