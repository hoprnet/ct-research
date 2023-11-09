import asyncio
from enum import Enum

from prometheus_client import Gauge

from .components.baseclass import Base
from .components.decorators import flagguard, formalin
from .components.horpd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.economic_model import EconomicModel
from .model.peer import Peer
from .model.subgraph_entry import SubgraphEntry
from .model.topology_entry import TopologyEntry
from .node import Node

SUBGRAPH_CALLS = Gauge("subgraph_calls", "# of subgraph calls", ["type"])
SUBGRAPH_SIZE = Gauge("subgraph_size", "Size of the subgraph")
TOPOLOGY_SIZE = Gauge("topology_size", "Size of the topology")
EXECUTIONS_COUNTER = Gauge("executions", "# of execution of the economic model")
ELIGIBLE_PEERS_COUNTER = Gauge("eligible_peers", "# of eligible peers for rewards")
APR_PER_PEER = Gauge("apr_per_peer", "APR per peer", ["peer_id"])
JOBS_PER_PEER = Gauge("jobs_per_peer", "Jobs per peer", ["peer_id"])
PEER_SPLIT_STAKE = Gauge("peer_split_stake", "Splitted stake", ["peer_id"])
PEER_TF_STAKE = Gauge("peer_tf_stake", "Transformed stake", ["peer_id"])
PEER_SAFE_COUNT = Gauge("peer_safe_count", "Number of safes", ["peer_id"])
DISTRIBUTION_DELAY = Gauge("distribution_delay", "Delay between two distributions")
NEXT_DISTRIBUTION_EPOCH = Gauge("next_distribution_s", "Next distribution (in seconds)")


class SubgraphType(Enum):
    DEFAULT = "default"
    BACKUP = "backup"
    NONE = "None"

    @classmethod
    def callables(cls):
        return [item for item in cls if item != cls.NONE]


class CTCore(Base):
    flag_prefix = "CORE_"

    def __init__(self):
        super().__init__()

        self.params = Parameters()

        self.nodes = list[Node]()

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.subgraph_list = LockedVar("subgraph_list", list[SubgraphEntry]())
        self.eligible_list = LockedVar("eligible_list", list[Peer]())

        self._selected_subgraph = SubgraphType.NONE
        self.selected_subgraph = SubgraphType.DEFAULT

        self.started = False

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
    def network_nodes_addresses(self) -> list[Address]:
        return [node.address for node in self.network_nodes]

    @property
    def selected_subgraph(self) -> SubgraphType:
        return self._selected_subgraph

    @selected_subgraph.setter
    def selected_subgraph(self, value: SubgraphType):
        if value != self.selected_subgraph:
            self._warning(f"Now using '{value.value}' subgraph.")

        self._selected_subgraph = value

    def subgraph_url(self, subgraph: SubgraphType) -> str:
        if subgraph == SubgraphType.DEFAULT:
            return self.params.subgraph_url

        if subgraph == SubgraphType.BACKUP:
            return self.params.subgraph_url_backup

        return SubgraphType.NONE

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
            "variables": {"first": 1, "skip": 0},
        }

        for subgraph in SubgraphType.callables():
            _, response = await Utils.httpPOST(self.subgraph_url(subgraph), data)

            if not response:
                continue

            SUBGRAPH_CALLS.labels(subgraph.value).inc()
            self.selected_subgraph = subgraph
            break
        else:
            self.selected_subgraph = SubgraphType.NONE

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
        if self.subgraph_url(self.selected_subgraph) == SubgraphType.NONE:
            self._warning("No subgraph URL available.")
            return

        data = {
            "query": self.params.subgraph_query,
            "variables": {"first": self.params.subgraph_pagination_size, "skip": 0},
        }

        safes = []
        while True:
            _, response = await Utils.httpPOST(
                self.subgraph_url(self.selected_subgraph), data
            )
            SUBGRAPH_CALLS.labels(self.selected_subgraph.value).inc()

            if "data" not in response:
                break

            safes.extend(response["data"]["safes"])

            if len(response["data"]["safes"]) >= self.params.subgraph_pagination_size:
                data["variables"]["skip"] += self.params.subgraph_pagination_size
            else:
                break

        results = list[SubgraphEntry]()
        for safe in safes:
            results.extend(
                [
                    SubgraphEntry.fromSubgraphResult(node)
                    for node in safe["registeredNodesInNetworkRegistry"]
                ]
            )

        await self.subgraph_list.set(results)

        SUBGRAPH_SIZE.set(len(results))
        self._debug(f"Fetched subgraph data ({len(results)} entries).")

    @flagguard
    @formalin("Getting topology data")
    async def get_topology_data(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        channels = await self.api.all_channels(False)
        if channels is None:
            self._warning("Topology data not available.")
            return

        results = await Utils.aggregatePeerBalanceInChannels(channels.all)
        topology_list = [TopologyEntry.fromDict(*arg) for arg in results.items()]

        await self.topology_list.set(topology_list)

        TOPOLOGY_SIZE.set(len(topology_list))
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

        model = EconomicModel.fromGCPFile(self.params.economic_model_filename)
        for peer in eligibles:
            peer.economic_model = model

        self._debug("Assigned economic model to eligible nodes.")

        excluded = Utils.rewardProbability(eligibles)
        self._debug(f"Excluded nodes with low stakes ({len(excluded)} entries).")

        await self.eligible_list.set(eligibles)

        # set prometheus metrics
        DISTRIBUTION_DELAY.set(model.delay_between_distributions)
        NEXT_DISTRIBUTION_EPOCH.set(
            Utils.nextEpoch(model.delay_between_distributions).timestamp()
        )
        ELIGIBLE_PEERS_COUNTER.set(len(eligibles))

        for peer in eligibles:
            APR_PER_PEER.labels(peer.address.id).set(peer.apr_percentage)
            JOBS_PER_PEER.labels(peer.address.id).set(peer.message_count_for_reward)
            PEER_SPLIT_STAKE.labels(peer.address.id).set(peer.split_stake)
            PEER_SAFE_COUNT.labels(peer.address.id).set(peer.safe_address_count)
            PEER_TF_STAKE.labels(peer.address.id).set(peer.transformed_stake)

    @flagguard
    @formalin("Distributing rewards")
    async def distribute_rewards(self):
        model = EconomicModel.fromGCPFile(self.params.economic_model_filename)

        delay = Utils.nextDelayInSeconds(model.delay_between_distributions)
        delay = 5
        self._debug(f"Waiting {delay} seconds for next distribution.")
        await asyncio.sleep(delay)

        min_peers = self.params.min_eligible_peers

        peers = list[Peer]()

        while len(peers) < min_peers:
            self._warning(f"Min. {min_peers} peers required to distribute rewards.")
            peers = await self.eligible_list.get()

            await asyncio.sleep(2)

        ### convert to csv
        attributes = Peer.attributesToExport()
        lines = [["peer_id"] + attributes]

        for peer in peers:
            line = [peer.address.id] + [getattr(peer, attr) for attr in attributes]
            lines.append(line)

        filename = Utils.generateFilename(
            self.params.gcp_file_prefix, self.params.gcp_folder
        )
        Utils.stringArrayToGCP(self.params.gcp_bucket, filename, lines)
        self._info(f"Distributed rewards to {len(peers)} peers.")

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
