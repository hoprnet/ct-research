import asyncio
from copy import deepcopy

from celery import Celery
from core.model.economic_model_sigmoid import EconomicModelSigmoid
from prometheus_client import Gauge

from .components.baseclass import Base
from .components.decorators import connectguard, flagguard, formalin
from .components.graphql_providers import (
    ProviderError,
    SafesProvider,
    StakingProvider,
    wxHOPRTransactionProvider,
    RewardsProvider
)
from .components.hoprd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.economic_model_legacy import EconomicModelLegacy
from .model.budget import Budget
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
EXECUTIONS_COUNTER = Gauge("executions", "# of execution of the economic model")
ELIGIBLE_PEERS_COUNTER = Gauge("eligible_peers", "# of eligible peers for rewards")
APR_PER_PEER = Gauge("apr_per_peer", "APR per peer", ["peer_id"])
JOBS_PER_PEER = Gauge("jobs_per_peer", "Jobs per peer", ["peer_id"])
PEER_SPLIT_STAKE = Gauge("peer_split_stake", "Splitted stake", ["peer_id"])
PEER_TF_STAKE = Gauge("peer_tf_stake", "Transformed stake", ["peer_id"])
PEER_SAFE_COUNT = Gauge("peer_safe_count", "Number of safes", ["peer_id"])
PEER_VERSION = Gauge("peer_version", "Peer version", ["peer_id", "version"])
DISTRIBUTION_DELAY = Gauge("distribution_delay", "Delay between two distributions")
NEXT_DISTRIBUTION_EPOCH = Gauge("next_distribution_epoch", "Next distribution (epoch)")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")


class Core(Base):
    def __init__(self):
        super().__init__()

        self.params = Parameters()

        self.nodes = list[Node]()

        self.budget: Budget = None
        self.legacy_model: EconomicModelSigmoid = None
        self.sigmoid_model: EconomicModelSigmoid = None

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)
        self.address = None

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.registered_nodes = LockedVar("subgraph_list", list[SubgraphEntry]())
        self.nft_holders = LockedVar("nft_holders", list[str]())
        self.eligible_list = LockedVar("eligible_list", list[Peer]())
        self.peer_rewards = LockedVar("peer_rewards", dict[str, float]())

        # subgraphs
        self._safe_subgraph_url = None
        self._staking_subgraph_url = None
        self._wxhopr_txs_subgraph_url = None

        # trick to have the subgraph in use displayed in the terminal
        self._subgraph_type = SubgraphType.NONE
        self.subgraph_type = SubgraphType.DEFAULT

        self.started = False

    def post_init(self, nodes: list[Node], params: Parameters):
        self.params = params
        self.nodes = nodes

        for node in self.nodes:
            node.params = params

        self.budget = Budget.fromParameters(self.params.economicModel.budget)

        self.legacy_model = EconomicModelLegacy.fromParameters(self.params.economicModel.legacy)
        self.sigmoid_model = EconomicModelSigmoid.fromParameters(self.params.economicModel.sigmoid)

        self.legacy_model.budget = deepcopy(self.budget)
        self.sigmoid_model.budget = deepcopy(self.budget)

        self._safe_subgraph_url = SubgraphURL(
            self.params.subgraph.deployerKey, self.params.subgraph.safesBalance
        )
        self._staking_subgraph_url = SubgraphURL(
            self.params.subgraph.deployerKey, self.params.subgraph.staking
        )
        self._wxhopr_txs_subgraph_url = SubgraphURL(
            self.params.subgraph.deployerKey, self.params.subgraph.wxHOPRTxs
        )

        self._rewards_subgraph_url = SubgraphURL(
            self.params.subgraph.deployerKey, self.params.subgraph.rewards
        )

    @property
    def print_prefix(self) -> str:
        return "ct-core"

    @property
    def api(self) -> HoprdAPI:
        return self.nodes[-1].api

    @property
    def network_nodes(self) -> list[Node]:
        return self.nodes[:-1]

    @property
    async def network_nodes_addresses(self) -> list[Address]:
        return await asyncio.gather(
            *[node.address.get() for node in self.network_nodes]
        )

    @property
    def subgraph_type(self) -> SubgraphType:
        return self._subgraph_type

    @property
    def safe_subgraph_url(self) -> str:
        return self._safe_subgraph_url(self.subgraph_type)

    @property
    def staking_subgraph_url(self) -> str:
        return self._staking_subgraph_url(self.subgraph_type)

    @property
    def wxhopr_txs_subgraph_url(self) -> str:
        return self._wxhopr_txs_subgraph_url(self.subgraph_type)

    @property
    def rewards_subgraph_url(self) -> str:
        return self._rewards_subgraph_url(self.subgraph_type)
    
    @subgraph_type.setter
    def subgraph_type(self, value: SubgraphType):
        if value != self.subgraph_type:
            self.warning(f"Now using '{value.value}' subgraph.")

        SUBGRAPH_IN_USE.set(value.toInt())
        self._subgraph_type = value

    async def _retrieve_address(self):
        addresses = await self.api.get_address("all")
        if not addresses:
            self.warning("No address retrieved from node.")
            return
        if "hopr" not in addresses or "native" not in addresses:
            self.warning("Invalid address retrieved from node.")
            return
        self.address = Address(addresses["hopr"], addresses["native"])

    @flagguard
    @formalin(None)
    async def healthcheck(self) -> dict:
        await self._retrieve_address()
        await self.connected.set(self.address is not None)

        self.debug(f"Connection state: {await self.connected.get()}")
        HEALTH.set(int(await self.connected.get()))

    @flagguard
    @formalin("Checking subgraph URLs")
    async def check_subgraph_urls(self):
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
        results = set[Peer]()

        for node in self.nodes:
            results.update(await node.peers.get())

        await self.all_peers.set(results)

        self.debug(f"Aggregated peers ({len(results)} entries).")
        UNIQUE_PEERS.set(len(results))

    @flagguard
    @formalin("Getting registered nodes")
    async def get_registered_nodes(self):
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
        topology = await self.topology_list.get()
        registered_nodes = await self.registered_nodes.get()
        peers = await self.all_peers.get()
        nft_holders = await self.nft_holders.get()

        self.debug(f"Topology size: {len(topology)}")
        self.debug(f"Subgraph size: {len(registered_nodes)}")
        self.debug(f"Network size: {len(peers)}")
        self.debug(f"NFT holders: {len(nft_holders)}")

        ready = len(topology) and len(registered_nodes) and len(peers)
        if not ready:
            self.warning("Not enough data to apply economic model.")
            return
        
        eligibles = Utils.mergeDataSources(topology, peers, registered_nodes)
        self.debug(f"Merged topology and subgraph data ({len(eligibles)} entries).")

        self.debug(f"after merge: {[el.address.id for el in eligibles]}")

        old_peer_addresses = [
            peer.address
            for peer in eligibles
            if peer.version_is_old(self.params.peer.minVersion)
        ]
        excluded = Utils.excludeElements(eligibles, old_peer_addresses)
        self.debug(
            f"Excluded peers running on old version (< {self.params.peer.minVersion}) ({len(excluded)} entries)."
        )
        self.debug(f"peers on wrong version: {[el.address.id for el in excluded]}")

        Utils.allowManyNodePerSafe(eligibles)
        self.debug(f"Allowed many nodes per safe ({len(eligibles)} entries).")

        low_allowance_addresses = [
            peer.address
            for peer in eligibles
            if peer.safe_allowance < self.params.economicModel.minSafeAllowance
        ]
        excluded = Utils.excludeElements(eligibles, low_allowance_addresses)
        self.debug(f"Excluded nodes with low safe allowance ({len(excluded)} entries).")
        self.debug(f"peers with low allowance {[el.address.id for el in excluded]}")

        excluded = Utils.excludeElements(eligibles, await self.network_nodes_addresses)
        self.debug(f"Excluded network nodes ({len(excluded)} entries).")

        if threshold := self.params.economicModel.NFTThreshold:
            low_stake_non_nft_holders = [
                peer.address
                for peer in eligibles
                if peer.safe_address not in nft_holders and peer.split_stake < threshold
            ]
            excluded = Utils.excludeElements(eligibles, low_stake_non_nft_holders)
            self.debug(
                f"Excluded non-nft-holders with stake < {threshold} ({len(excluded)} entries)."
            )

        low_stake_addresses = [
            peer.address
            for peer in eligibles
            if peer.split_stake < self.model.coefficients.l
        ]
        excluded = Utils.excludeElements(eligibles, low_stake_addresses)
        self.debug(f"Excluded nodes with low stake ({len(excluded)} entries).")

        redeemed_rewards = await self.peer_rewards.get()
        for peer in eligibles:
            peer.economic_model = deepcopy(self.model)
            peer.economic_model.coefficients.c += redeemed_rewards.get(peer.address.address,0.0)

        self.info(f"Assigned economic model to eligible nodes. ({len(eligibles)} entries).")

        self.debug(f"Final eligible list {[el.address.id for el in eligibles]}")

        await self.eligible_list.set(eligibles)

        # set prometheus metrics
        DISTRIBUTION_DELAY.set(self.model.delay_between_distributions)
        NEXT_DISTRIBUTION_EPOCH.set(
            Utils.nextEpoch(self.model.delay_between_distributions).timestamp()
        )
        ELIGIBLE_PEERS_COUNTER.set(len(eligibles))

        for peer in eligibles:
            JOBS_PER_PEER.labels(peer.address.id).set(peer.message_count_for_reward)
            PEER_SPLIT_STAKE.labels(peer.address.id).set(peer.split_stake)
            PEER_SAFE_COUNT.labels(peer.address.id).set(peer.safe_address_count)
            PEER_TF_STAKE.labels(peer.address.id).set(peer.transformed_stake)
            PEER_VERSION.labels(peer.address.id, peer.version).set(1)

    @flagguard
    @formalin("Distributing rewards")
    async def distribute_rewards(self):
        delay = Utils.nextDelayInSeconds(self.budget.delay_between_distributions)
        self.debug(f"Waiting {delay} seconds for next distribution.")
        await asyncio.sleep(delay)

        min_peers = self.params.distribution.minEligiblePeers

        peers = list[Peer]()

        while len(peers) < min_peers:
            peers = await self.eligible_list.get()
            self.warning(
                f"Min. {min_peers} peers required to distribute rewards (having {len(peers)})."
            )
            await asyncio.sleep(2)

        # convert to csv and store on GCP
        filename = Utils.generateFilename(
            self.params.gcp.filePrefix, self.params.gcp.folder
        )
        lines = Peer.toCSV(peers)
        Utils.stringArrayToGCP(self.params.gcp.bucket, filename, lines)

        # create celery tasks
        app = Celery(
            name=self.params.rabbitmq.projectName,
            broker=f"amqp://{self.params.rabbitmq.username}:{self.params.rabbitmq.password}@{self.params.rabbitmq.host}/{self.params.rabbitmq.virtualhost}",
        )
        app.autodiscover_tasks(force=True)

        for peer in peers:
            legacy_count = self.legacy_model.message_count_for_reward(peer.split_stake)
            sigmoid_count = self.sigmoid_model.message_count_for_reward(peer.split_stake)

            Utils.taskSendMessage(
                app,
                peer.address.id,
                legacy_count + sigmoid_count,
                self.budget.ticket_price,
                task_name=self.params.rabbitmq.taskName,
            )
        self.info(f"Distributed rewards to {len(peers)} peers.")

        EXECUTIONS_COUNTER.inc()

    @flagguard
    @formalin("Getting funding data")
    @connectguard
    async def get_fundings(self):
        ct_safe_addresses = {
            getattr(await node.api.node_info(), "node_safe", None)
            for node in self.network_nodes
        }

        provider = wxHOPRTransactionProvider(self.wxhopr_txs_subgraph_url)

        transactions = list[dict]()
        for to_address in ct_safe_addresses:
            try:
                for transaction in await provider.get(to=to_address):
                    transactions.append(transaction)

            except ProviderError as err:
                self.error(f"get_fundings: {err}")

        total_funding = sum([float(tx["amount"]) for tx in transactions])
        self.debug(f"Total funding: {total_funding}")
        TOTAL_FUNDING.set(total_funding)

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
                results[account["id"]] = account["redeemedValue"]

        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")

        await self.peer_rewards.set(results)

        self.debug(f"Fetched peers rewards amounts ({len(results)} entries).")

    async def start(self):
        """
        Start the node.
        """
        self.info(f"CTCore started with {len(self.network_nodes)} nodes.")

        if len(self.network_nodes) == 0:
            self.error("No nodes available, exiting.")
            return

        if self.tasks:
            return

        for node in self.network_nodes:
            node.started = True
            await node._retrieve_address()
            self.tasks.update(node.tasks())

        self.started = True

        self.tasks.add(asyncio.create_task(self.healthcheck()))
        self.tasks.add(asyncio.create_task(self.check_subgraph_urls()))
        self.tasks.add(asyncio.create_task(self.get_fundings()))
        self.tasks.add(asyncio.create_task(self.get_peers_rewards()))

        self.tasks.add(asyncio.create_task(self.aggregate_peers()))
        self.tasks.add(asyncio.create_task(self.get_registered_nodes()))
        self.tasks.add(asyncio.create_task(self.get_topology_data()))
        self.tasks.add(asyncio.create_task(self.get_nft_holders()))

        self.tasks.add(asyncio.create_task(self.apply_economic_model()))
        self.tasks.add(asyncio.create_task(self.distribute_rewards()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stop the node.
        """
        self.started = False

        for node in self.network_nodes:
            node.started = False

        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()
