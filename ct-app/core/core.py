import asyncio

from celery import Celery
from prometheus_client import Gauge

from .components.baseclass import Base
from .components.decorators import connectguard, flagguard, formalin
from .components.hoprd_api import HoprdAPI
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model.address import Address
from .model.economic_model import EconomicModel
from .model.peer import Peer
from .model.subgraph_entry import SubgraphEntry
from .model.subgraph_type import SubgraphType
from .model.topology_entry import TopologyEntry
from .node import Node

HEALTH = Gauge("core_health", "Node health")
UNIQUE_PEERS = Gauge("unique_peers", "Unique peers")
SUBGRAPH_IN_USE = Gauge("subgraph_in_use", "Subgraph in use")
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
NEXT_DISTRIBUTION_EPOCH = Gauge("next_distribution_epoch", "Next distribution (epoch)")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")


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

        self.app = Celery(
            name=self.params.rabbitmq.project_name,
            broker=f"amqp://{self.params.rabbitmq.username}:{self.params.rabbitmq.password}@{self.params.rabbitmq.host}/{self.params.rabbitmq.virtualhost}",
        )
        self.app.autodiscover_tasks(force=True)

        self._safes_balance_subgraph_type = (
            SubgraphType.NONE
        )  # trick to have the subgraph in use displayed in the terminal

        self.safes_balance_subgraph_type = SubgraphType.DEFAULT

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
    def safes_balance_subgraph_type(self) -> SubgraphType:
        return self._safes_balance_subgraph_type

    @safes_balance_subgraph_type.setter
    def safes_balance_subgraph_type(self, value: SubgraphType):
        if value != self.safes_balance_subgraph_type:
            self.warning(f"Now using '{value.value}' subgraph.")

        SUBGRAPH_IN_USE.set(value.toInt())
        self._safes_balance_subgraph_type = value

    def subgraph_safes_balance_url(self, subgraph: SubgraphType) -> str:
        if subgraph == SubgraphType.DEFAULT:
            return self.params.subgraph.safes_balance_url

        if subgraph == SubgraphType.BACKUP:
            return self.params.subgraph.safes_balance_url_backup

        return SubgraphType.NONE

    async def _retrieve_address(self):
        addresses = await self.api.get_address("all")
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
        data = {
            "query": self.params.subgraph.safes_balance_query,
            "variables": {"first": 1, "skip": 0},
        }

        for subgraph in SubgraphType.callables():
            _, response = await Utils.httpPOST(
                self.subgraph_safes_balance_url(subgraph), data
            )

            if not response:
                continue

            SUBGRAPH_CALLS.labels(subgraph.value).inc()
            self.safes_balance_subgraph_type = subgraph
            break
        else:
            self.safes_balance_subgraph_type = SubgraphType.NONE

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
    @formalin("Getting subgraph data")
    async def get_subgraph_data(self):
        if self.safes_balance_subgraph_type == SubgraphType.NONE:
            self.warning("No subgraph URL available.")
            return

        safes = []
        skip = 0

        while True:
            query = self.params.subgraph.safes_balance_query
            query = query.replace("valfirst", f"{self.params.subgraph.pagination_size}")
            query = query.replace("valskip", f"{skip}")

            _, response = await Utils.httpPOST(
                self.subgraph_safes_balance_url(self.safes_balance_subgraph_type),
                {"query": query},
            )
            SUBGRAPH_CALLS.labels(self.safes_balance_subgraph_type.value).inc()

            if not response:
                self.warning("No response from subgraph.")
                break

            if "data" not in response:
                self.warning("No data in response from subgraph.")
                break

            safes.extend(response["data"]["safes"])

            print(f"{response['data']['safes']=}")
            if len(response["data"]["safes"]) >= self.params.subgraph.pagination_size:
                skip += self.params.subgraph.pagination_size
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
        self.debug(f"Fetched subgraph data ({len(results)} entries).")

    @flagguard
    @connectguard
    @formalin("Getting topology data")
    async def get_topology_data(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        channels = await self.api.all_channels(False)
        if channels is None:
            self.warning("Topology data not available.")
            return

        results = await Utils.aggregatePeerBalanceInChannels(channels.all)
        topology_list = [TopologyEntry.fromDict(*arg) for arg in results.items()]

        await self.topology_list.set(topology_list)

        TOPOLOGY_SIZE.set(len(topology_list))
        self.debug(f"Fetched topology links ({len(topology_list)} entries).")

    @flagguard
    @formalin("Applying economic model")
    async def apply_economic_model(self):
        ready: bool = False

        while not ready:
            topology = await self.topology_list.get()
            subgraph = await self.subgraph_list.get()
            peers = await self.all_peers.get()

            self.debug(f"Topology size: {len(topology)}")
            self.debug(f"Subgraph size: {len(subgraph)}")
            self.debug(f"Network size: {len(peers)}")

            ready = len(topology) and len(subgraph) and len(peers)
            await asyncio.sleep(2)

        eligibles = Utils.mergeTopologyPeersSubgraph(topology, peers, subgraph)
        self.debug(f"Merged topology and subgraph data ({len(eligibles)} entries).")

        Utils.allowManyNodePerSafe(eligibles)
        self.debug(f"Allowed many nodes per safe ({len(eligibles)} entries).")

        print(f"{self.params.economic_model.min_safe_allowance=}")
        low_allowance_addresses = [
            peer.address
            for peer in eligibles
            if peer.safe_allowance < self.params.economic_model.min_safe_allowance
        ]
        excluded = Utils.excludeElements(eligibles, low_allowance_addresses)
        self.debug(f"Excluded nodes with low safe allowance ({len(excluded)} entries).")

        excluded = Utils.excludeElements(eligibles, self.network_nodes_addresses)
        self.debug(f"Excluded network nodes ({len(excluded)} entries).")

        self.debug(f"Eligible nodes ({len(eligibles)} entries).")

        model = EconomicModel.fromGCPFile(
            self.params.gcp.bucket, self.params.economic_model.filename
        )
        for peer in eligibles:
            peer.economic_model = model

        self.debug("Assigned economic model to eligible nodes.")

        excluded = Utils.rewardProbability(eligibles)
        self.debug(f"Excluded nodes with low stakes ({len(excluded)} entries).")

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
        model = EconomicModel.fromGCPFile(
            self.params.gcp.bucket, self.params.economic_model.filename
        )

        delay = Utils.nextDelayInSeconds(model.delay_between_distributions)
        self.debug(f"Waiting {delay} seconds for next distribution.")

        await asyncio.sleep(delay)

        min_peers = self.params.distribution.min_eligible_peers

        peers = list[Peer]()

        while len(peers) < min_peers:
            peers = await self.eligible_list.get()
            self.warning(
                f"Min. {min_peers} peers required to distribute rewards (having {len(peers)})."
            )
            await asyncio.sleep(2)

        # convert to csv and store on GCP
        filename = Utils.generateFilename(
            self.params.gcp.file_prefix, self.params.gcp.folder
        )
        lines = Peer.toCSV(peers)
        Utils.stringArrayToGCP(self.params.gcp.bucket, filename, lines)

        # create celery tasks
        for peer in peers:
            Utils.taskSendMessage(
                self.app,
                peer.address.id,
                peer.message_count_for_reward,
                peer.economic_model.budget.ticket_price,
                task_name=self.params.rabbitmq.task_name,
            )
        self.info(f"Distributed rewards to {len(peers)} peers.")

        EXECUTIONS_COUNTER.inc()

    @flagguard
    @formalin("Getting funding data")
    async def get_fundings(self):
        from_address = self.params.subgraph.from_address
        ct_safe_addresses = {
            (await node.api.node_info()).node_safe for node in self.network_nodes
        }

        transactions = []
        for to_address in ct_safe_addresses:
            if to_address is None:
                continue

            query: str = self.params.subgraph.wxhopr_txs_query
            query = query.replace("valfrom", f'"{from_address}"')
            query = query.replace("valto", f'"{to_address}"')

            _, response = await Utils.httpPOST(
                self.params.subgraph.wxhopr_txs_url, {"query": query}
            )

            if not response:
                self.warning("No response from subgraph.")
                break

            if "data" not in response:
                self.warning("No data in response from subgraph.")
                break

            transactions.extend(response["data"]["transactions"])

        total_funding = sum([float(tx["amount"]) for tx in transactions])
        self.debug(f"Total funding: {total_funding}")
        TOTAL_FUNDING.set(total_funding)

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
