import asyncio

import aiohttp

from tools.hopr_api_helper import HoprdAPIHelper

from .components.baseclass import Base
from .components.decorators import flagguard, formalin
from .components.lockedvar import LockedVar
from .components.parameters import Parameters
from .components.utils import Utils
from .model import Address, Peer, SubgraphEntry, TopologyEntry
from .node import Node


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
        results = list[SubgraphEntry]()

        data = {
            "query": self.params.subgraph_query,
            "variables": {"first": self.params.subgraph_pagination_size, "skip": 0},
        }

        safes = []
        while True:
            async with aiohttp.ClientSession() as session:
                _, response = await Utils.doPost(
                    session, self.params.subgraph_url, data
                )

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
