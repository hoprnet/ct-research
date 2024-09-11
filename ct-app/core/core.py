# region Imports
import asyncio
import random

from prometheus_client import Gauge

from .components import AsyncLoop, Base, HoprdAPI, LockedVar, Parameters, Utils
from .components.decorators import connectguard, flagguard, formalin
from .model import Address, Peer
from .model.economic_model import EconomicModelLegacy, EconomicModelSigmoid
from .model.subgraph import (
    AllocationEntry,
    AllocationsProvider,
    BalanceEntry,
    EOABalanceProvider,
    NodeEntry,
    ProviderError,
    RewardsProvider,
    SafesProvider,
    StakingProvider,
    SubgraphType,
    SubgraphURL,
    TopologyEntry,
)
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

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.registered_nodes_list = LockedVar("subgraph_list", list[NodeEntry]())
        self.nft_holders_list = LockedVar("nft_holders_list", list[str]())
        self.allocations_data = LockedVar("allocations_data", list[AllocationEntry]())
        self.eoa_balances_data = LockedVar("eoa_balances_data", list[BalanceEntry]())
        self.peer_rewards = LockedVar("peer_rewards", dict[str, float]())

        # self.subgraph_type = SubgraphType.DEFAULT

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

        self.safe_sg_url = SubgraphURL(self.params.subgraph, "safesBalance")[value]
        self.staking_sg_url = SubgraphURL(self.params.subgraph, "staking")[value]
        self.rewards_sg_url = SubgraphURL(self.params.subgraph, "rewards")[value]
        self.mainnet_allocation_sg_url = SubgraphURL(
            self.params.subgraph, "mainnetAllocations"
        )[value]
        self.gnosis_allocation_sg_url = SubgraphURL(
            self.params.subgraph, "gnosisAllocations"
        )[value]
        self.mainnet_balances_sg_url = SubgraphURL(
            self.params.subgraph, "hoprOnMainet"
        )[value]
        self.gnosis_balances_sg_url = SubgraphURL(self.params.subgraph, "hoprOnGnosis")[
            value
        ]

        SUBGRAPH_IN_USE.set(value.toInt())
        self._subgraph_type = value

    @flagguard
    @formalin
    async def rotate_subgraphs(self):
        """
        Checks the subgraph URLs and sets the subgraph type in use (default, backup or none)
        """
        if self.params.subgraph.type == "auto":
            for type in SubgraphType.callables():
                self.subgraph_type = type
                if await SafesProvider(self.safe_sg_url).test():
                    break
            else:
                self.subgraph_type = SubgraphType.NONE

        else:
            self.subgraph_type = getattr(
                SubgraphType, self.params.subgraph.type.upper(), SubgraphType.NONE
            )
            self.warning(f"Using static {self.subgraph_type} subgraph endpoint")

        SUBGRAPH_CALLS.labels(self.subgraph_type.value).inc()

    @flagguard
    @formalin
    async def connected_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """

        async with self.all_peers.lock:
            visible_peers = set[Peer]()

            known_peers: set[Peer] = self.all_peers.value

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

            self.all_peers.value = known_peers

            self.debug(f"Aggregated peers ({len(known_peers)} entries).")
            UNIQUE_PEERS.set(len(known_peers))

    @flagguard
    @formalin
    async def registered_nodes(self):
        """
        Gets the subgraph data and sets the subgraph_list LockedVar.
        """
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = SafesProvider(self.safe_sg_url)
        results = list[NodeEntry]()
        try:
            for safe in await provider.get():
                entries = [
                    NodeEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
                results.extend(entries)

        except ProviderError as err:
            self.error(f"get_registered_nodes: {err}")

        await self.registered_nodes_list.set(results)

        SUBGRAPH_SIZE.set(len(results))
        self.debug(f"Fetched registered nodes ({len(results)} entries).")

    @flagguard
    @formalin
    async def nft_holders(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = StakingProvider(self.staking_sg_url)

        results = list[str]()
        try:
            for nft in await provider.get():
                if owner := nft.get("owner", {}).get("id", None):
                    results.append(owner)

        except ProviderError as err:
            self.error(f"nft_holders: {err}")

        await self.nft_holders_list.set(results)

        NFT_HOLDERS.set(len(results))
        self.debug(f"Fetched NFT holders ({len(results)} entries).")

    @flagguard
    @formalin
    async def allocations(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        mainnet_provider = AllocationsProvider(self.mainnet_allocation_sg_url)
        gnosis_provider = AllocationsProvider(self.gnosis_allocation_sg_url)

        results = list[AllocationEntry]()
        try:
            for account in await mainnet_provider.get():
                results.append(AllocationEntry(**account["account"]))
        except ProviderError as err:
            self.error(f"allocations: {err}")

        try:
            for account in await gnosis_provider.get():
                results.append(AllocationEntry(**account["account"]))
        except ProviderError as err:
            self.error(f"allocations: {err}")

        await self.allocations_data.set(results)
        self.debug(f"Fetched allocations ({len(results)} entries).")

    @flagguard
    @formalin
    async def eoa_balances(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        mainnet_provider = EOABalanceProvider(self.mainnet_balances_sg_url)
        gnosis_provider = EOABalanceProvider(self.gnosis_balances_sg_url)

        addresses = [alloc.address for alloc in await self.allocations_data.get()]
        if len(addresses) == 0:
            self.info("No investors addresses found.")
            return
        else:
            balances = {address: 0 for address in addresses}

        try:
            for account in await mainnet_provider.get(id_in=list(balances.keys())):
                balances[account["id"]] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        try:
            for account in await gnosis_provider.get(id_in=list(balances.keys())):
                balances[account["id"]] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        eoa_balances = [BalanceEntry(key, value) for key, value in balances.items()]

        await self.eoa_balances_data.set(eoa_balances)
        self.debug(f"Fetched EOA balances ({len(balances)} entries).")

    @flagguard
    @formalin
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
    @formalin
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        nodes = await self.registered_nodes_list.get()
        nft_holders = await self.nft_holders_list.get()
        topology = await self.topology_list.get()
        ct_nodes = await self.ct_nodes_addresses
        redeemed_rewards = await self.peer_rewards.get()
        eoa_balances = await self.eoa_balances_data.get()
        allocations: list[AllocationEntry] = await self.allocations_data.get()

        async with self.all_peers.lock:
            peers = self.all_peers.value

            Utils.associateAllocationsAndSafes(allocations, nodes)
            Utils.associateEOABalancesAndSafes(eoa_balances, nodes)

            if not all([len(topology), len(nodes), len(peers)]):
                self.warning("Not enough data to apply economic model.")
                return

            await Utils.mergeDataSources(
                topology, peers, nodes, allocations, eoa_balances
            )

            for p in peers:
                if p.is_old(self.params.peer.minVersion):
                    await p.yearly_message_count.set(None)

            Utils.allowManyNodePerSafe(peers)

            for p in peers:
                if not p.is_eligible(
                    self.params.economicModel.minSafeAllowance,
                    self.legacy_model.coefficients.l,
                    ct_nodes,
                    nft_holders,
                    self.params.economicModel.NFTThreshold,
                ):
                    await p.yearly_message_count.set(None)

            economic_security = (
                sum(
                    [
                        p.split_stake
                        for p in peers
                        if (await p.yearly_message_count.get()) is not None
                    ]
                )
                / self.params.economicModel.sigmoid.totalTokenSupply
            )
            network_capacity = (
                len(
                    [
                        p
                        for p in peers
                        if (await p.yearly_message_count.get()) is not None
                    ]
                )
                / self.params.economicModel.sigmoid.networkCapacity
            )
            sigmoid_model_input = [economic_security, network_capacity]

            for peer in peers:
                if await peer.yearly_message_count.get() is None:
                    continue

                legacy_message_count = self.legacy_model.yearly_message_count(
                    peer.split_stake, redeemed_rewards.get(peer.address.address, 0.0)
                )
                sigmoid_message_count = self.sigmoid_model.yearly_message_count(
                    peer.split_stake, sigmoid_model_input
                )

                await peer.yearly_message_count.set(
                    legacy_message_count + sigmoid_message_count
                )
                MESSAGE_COUNT.labels(peer.address.id, "legacy").set(
                    legacy_message_count
                )
                MESSAGE_COUNT.labels(peer.address.id, "sigmoid").set(
                    sigmoid_message_count
                )

            eligibles = [
                p for p in peers if await p.yearly_message_count.get() is not None
            ]
            self.info(f"Eligible nodes: {len(eligibles)} entries.")
            ELIGIBLE_PEERS.set(len(eligibles))

            self.all_peers.value = set(peers)

    @flagguard
    @formalin
    async def peers_rewards(self):
        if self.subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        provider = RewardsProvider(self.rewards_sg_url)

        results = dict()
        try:
            for account in await provider.get():
                results[account["id"]] = float(account["redeemedValue"])

        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")

        await self.peer_rewards.set(results)

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
            ]
        )

        for node in self.nodes:
            AsyncLoop.add(node.watch_message_queue)

        await AsyncLoop.gather()
