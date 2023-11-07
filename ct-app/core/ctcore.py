import asyncio

from prometheus_client import Gauge
from tools.hopr_api_helper import HoprdAPIHelper

from .components.baseclass import Base
from .components.decorators import flagguard, formalin
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model import Address, Peer, SubgraphEntry, TopologyEntry
from .node import Node

EXECUTIONS_COUNTER = Gauge("executions", "# of execution of the economic model")
ELIGIBLE_PEERS_COUNTER = Gauge("eligible_peers", "# of eligible peers for rewards")
BUDGET = Gauge("budget", "Budget for the economic model")
BUDGET_PERIOD = Gauge("budget_period", "Budget period for the economic model")
DISTRIBUTION_FREQUENCY = Gauge("dist_freq", "Number of expected distributions")
TICKET_PRICE = Gauge("ticket_price", "Ticket price")
TICKET_WINNING_PROB = Gauge("ticket_winning_prob", "Ticket winning probability")
APY_PER_PEER = Gauge("apy_per_peer", "APY per peer", ["peer_id"])
JOBS_PER_PEER = Gauge("jobs_per_peer", "Jobs per peer", ["peer_id"])
PEER_SPLIT_STAKE = Gauge("peer_split_stake", "Splitted stake", ["peer_id"])
PEER_TF_STAKE = Gauge("peer_tf_stake", "Transformed stake", ["peer_id"])
PEER_SAFE_COUNT = Gauge("peer_safe_count", "Number of safes", ["peer_id"])


class CTCore(Base):
    flag_prefix = "CORE_"

    def __init__(self):
        self.params = Parameters()

        self.nodes = list[Node]()

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.subgraph_list = LockedVar("subgraph_list", list[SubgraphEntry]())
        self.eligible_list = LockedVar("eligible_list", list[Peer]())

        self.subgraph_url = None

        self.started = False

    @property
    def print_prefix(self) -> str:
        return "ct-core"

    @property
    def api(self) -> HoprdAPIHelper:
        return self.nodes[-1].api

    @property
    def network_nodes(self) -> list[Node]:
        return self.nodes[:-1]

    @property
    def network_nodes_addresses(self) -> list[Address]:
        return [node.address for node in self.network_nodes]

    @flagguard
    @formalin("Running healthcheck")
    async def healthcheck(self):
        states = [await node.connected.get() for node in self.network_nodes]
        await self.connected.set(all(states))

        self._debug(f"Connection state: {await self.connected.get()}")

    @flagguard
    @formalin("Checking subgraph URLs")
    async def check_subgraph_urls(self):
        data = {
            "query": self.params.subgraph_query,
            "variables": {"first": self.params.subgraph_pagination_size, "skip": 0},
        }

        if await Utils.httpPOST(self.params.subgraph_url, data):
            if self.subgraph_url != self.params.subgraph_url:
                self._info("Subgraph URL changed to 'standard'")
            self.subgraph_url = self.params.subgraph_url
            return

        if await Utils.httpPOST(self.params.subgraph_url_backup, data):
            if self.subgraph_url != self.params.subgraph_url_backup:
                self._info("Subgraph URL changed to 'backup'")
            self.subgraph_url = self.params.subgraph_url_backup
            return

        if self.subgraph_url is not None:
            self._warning("Subgraph URL changed to 'None'")
        self.subgraph_url = None

    @flagguard
    @formalin("Aggregating peers")
    async def aggregate_peers(self):
        results = set[Peer]()

        for node in self.nodes:
            results.update(await node.peers.get())

        await self.all_peers.set(results)

        self._debug(f"Aggregated peers ({len(results)} entries).")

    @flagguard
    @formalin("Getting subgraph data")
    async def get_subgraph_data(self):
        if not self.subgraph_url:
            self._warning("No subgraph URL available.")
            return

        results = list[SubgraphEntry]()

        data = {
            "query": self.params.subgraph_query,
            "variables": {"first": self.params.subgraph_pagination_size, "skip": 0},
        }

        safes = []
        while True:
            _, response = await Utils.httpPOST(self.subgraph_url, data)

            if "data" not in response:
                break

            safes.extend(response["data"]["safes"])

            if len(response["data"]["safes"]) >= self.params.subgraph_pagination_size:
                data["variables"]["skip"] += self.params.subgraph_pagination_size
            else:
                break

        for safe in safes:
            results.extend(
                [
                    SubgraphEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
            )

        await self.subgraph_list.set(results)

        self._debug(f"Fetched subgraph data ({len(results)} entries).")

    @flagguard
    @formalin("Getting topology data")
    async def get_topology_data(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        results = await self.api.get_unique_nodeAddress_peerId_aggbalance_links()
        topology_list = [
            TopologyEntry.fromDict(key, value) for key, value in results.items()
        ]

        await self.topology_list.set(topology_list)

        self._debug(f"Fetched topology links ({len(topology_list)} entries).")

    @flagguard
    @formalin("Applying economic model")
    async def apply_economic_model(self):
        ready: bool = False

        while not ready:
            topology = await self.topology_list.get()
            subgraph = await self.subgraph_list.get()
            peers = await self.all_peers.get()

            ready = len(topology) and len(subgraph) and len(peers)
            await asyncio.sleep(1)

        eligibles = Utils.mergeTopologyPeersSubgraph(topology, peers, subgraph)
        self._debug(f"Merged topology and subgraph data ({len(eligibles)} entries).")

        Utils.allowManyNodePerSafe(eligibles)
        self._debug(f"Allowed many nodes per safe ({len(eligibles)} entries).")

        excluded = Utils.excludeElements(eligibles, self.network_nodes_addresses)
        self._debug(f"Excluded network nodes ({len(excluded)} entries).")
        self._debug(f"Eligible nodes ({len(eligibles)} entries).")

        model = Utils.EconomicModelFromGCPFile(self.params.economic_model_filename)
        for peer in eligibles:
            peer.economic_model = model

        self._debug("Assigned economic model to eligible nodes.")

        excluded = Utils.rewardProbability(eligibles)
        self._debug(f"Excluded nodes with low stakes ({len(excluded)} entries).")

        await self.eligible_list.set(eligibles)

        # set prometheus metrics
        BUDGET.set(model.budget.budget)
        BUDGET_PERIOD.set(model.budget.period)
        DISTRIBUTION_FREQUENCY.set(model.budget.distribution_frequency)
        TICKET_PRICE.set(model.budget.ticket_price)
        TICKET_WINNING_PROB.set(model.budget.winning_probability)

        ELIGIBLE_PEERS_COUNTER.set(len(eligibles))
        for peer in eligibles:
            APY_PER_PEER.labels(peer.id).set(peer.apy_percentage)
            JOBS_PER_PEER.labels(peer.id).set(peer.message_count_for_reward)
            PEER_SPLIT_STAKE.labels(peer.id).set(peer.split_stake)
            PEER_SAFE_COUNT.labels(peer.id).set(peer.safe_address_count)
            PEER_TF_STAKE.labels(peer.id).set(peer.transformed_stake)

    @flagguard
    @formalin("Distributing rewards")
    async def distribute_rewards(self):
        ready = False
        min_peers = self.params.min_eligible_peers

        while not ready:
            peers = await self.eligible_list.get()

            if len(peers) >= min_peers:
                ready = True
            else:
                self._warning(f"Min. {min_peers} peers required to distribute rewards.")
                await asyncio.sleep(2)

        self._info(f"Distributing rewards to {len(peers)} peers.")

        EXECUTIONS_COUNTER.inc()

    async def start(self):
        """
        Start the node.
        """
        self._info(f"CTCore started with {len(self.network_nodes)} nodes.")

        if self.tasks:
            return

        for node in self.network_nodes:
            node.started = True
            await node._retrieve_address()
            self.tasks.update(node.tasks())

        self.started = True

        self.tasks.add(asyncio.create_task(self.healthcheck()))
        self.tasks.add(asyncio.create_task(self.check_subgraph_urls()))

        self.tasks.add(asyncio.create_task(self.aggregate_peers()))
        self.tasks.add(asyncio.create_task(self.get_subgraph_data()))
        self.tasks.add(asyncio.create_task(self.get_topology_data()))

        self.tasks.add(asyncio.create_task(self.apply_economic_model()))
        self.tasks.add(asyncio.create_task(self.distribute_rewards()))

        await asyncio.gather(*self.tasks)  # , return_exceptions=True)

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
