import asyncio
import random
import time
from copy import deepcopy
from datetime import datetime
from typing import Any

from database.database_connection import DatabaseConnection
from database.models import Reward
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
from .model.budget import Budget
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
EXECUTIONS_COUNTER = Gauge("executions", "# of execution of the economic model")
ELIGIBLE_PEERS_COUNTER = Gauge("eligible_peers", "# of eligible peers for rewards")
APR_PER_PEER = Gauge("apr_per_peer", "APR per peer", ["peer_id"])
JOBS_PER_PEER = Gauge("jobs_per_peer", "Jobs per peer", ["peer_id", "model"])
PEER_SPLIT_STAKE = Gauge("peer_split_stake", "Splitted stake", ["peer_id"])
PEER_TF_STAKE = Gauge("peer_tf_stake", "Transformed stake", ["peer_id"])
PEER_SAFE_COUNT = Gauge("peer_safe_count", "Number of safes", ["peer_id"])
PEER_VERSION = Gauge("peer_version", "Peer version", ["peer_id", "version"])
DISTRIBUTION_DELAY = Gauge("distribution_delay", "Delay between two distributions")
NEXT_DISTRIBUTION_EPOCH = Gauge("next_distribution_epoch", "Next distribution (epoch)")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")


class Core(Base):
    """
    The Core class represents the main class of the application. It is responsible for managing the nodes, the economic model and the distribution of rewards.
    """

    def __init__(self):
        super().__init__()

        self.params = Parameters()

        self.nodes = list[Node]()

        self.legacy_model: EconomicModelLegacy = None
        self.sigmoid_model: EconomicModelSigmoid = None
        self._budget: Budget = None

        self.tasks = set[asyncio.Task]()

        self.connected = LockedVar("connected", False)
        self.address = None

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_list = LockedVar("topology_list", list[TopologyEntry]())
        self.registered_nodes = LockedVar("subgraph_list", list[SubgraphEntry]())
        self.nft_holders = LockedVar("nft_holders", list[str]())
        self.eligible_list = LockedVar("eligible_list", list[Peer]())
        self.peer_rewards = LockedVar("peer_rewards", dict[str, float]())
        self.ticket_price = LockedVar("ticket_price", 1.0)

        # subgraphs
        self._safe_subgraph_url = None
        self._staking_subgraph_url = None
        self._rewards_subgraph_url = None

        # trick to have the subgraph in use displayed in the terminal
        self._subgraph_type = SubgraphType.NONE
        self.subgraph_type = SubgraphType.DEFAULT

        self.started = False

    def post_init(self, nodes: list[Node], params: Parameters):
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
        self.budget = Budget(self.params.economicModel.intervals)

        self._safe_subgraph_url = SubgraphURL(
            self.params.subgraph.apiKey, self.params.subgraph.safesBalance
        )
        self._staking_subgraph_url = SubgraphURL(
            self.params.subgraph.apiKey, self.params.subgraph.staking
        )

        self._rewards_subgraph_url = SubgraphURL(
            self.params.subgraph.apiKey, self.params.subgraph.rewards
        )

    @property
    def budget(self):
        return self._budget

    @budget.setter
    def budget(self, value: Budget):
        self._budget = value
        self.legacy_model.budget = value
        self.sigmoid_model.budget = value

    @property
    def print_prefix(self) -> str:
        return "ct-core"

    @property
    def api(self) -> HoprdAPI:
        return random.choice(self.nodes).api

    @property
    async def network_nodes_addresses(self) -> list[Address]:
        return await asyncio.gather(*[node.address.get() for node in self.nodes])

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
            self.info(f"Now using '{value.value}' subgraph.")

        SUBGRAPH_IN_USE.set(value.toInt())
        self._subgraph_type = value

    async def _retrieve_address(self):
        """
        Retrieves the address from the node.
        """
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
        results = set[Peer]()

        for node in self.nodes:
            results.update(await node.peers.get())

        await self.all_peers.set(results)

        self.debug(f"Aggregated peers ({len(results)} entries).")
        UNIQUE_PEERS.set(len(results))

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
        Applies the economic model to the eligible peers (after multiple filtering layers) and sets the eligible_list LockedVar.
        """
        topology = await self.topology_list.get()
        registered_nodes = await self.registered_nodes.get()
        peers = await self.all_peers.get()
        nft_holders = await self.nft_holders.get()

        self.info(f"Topology size: {len(topology)}")
        self.info(f"Subgraph size: {len(registered_nodes)}")
        self.info(f"Network size: {len(peers)}")
        self.info(f"NFT holders: {len(nft_holders)}")

        ready = len(topology) and len(registered_nodes) and len(peers)
        if not ready:
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
    @formalin("Distributing rewards")
    @connectguard
    async def distribute_rewards(self):
        delay = Utils.nextDelayInSeconds(self.params.economicModel.intervals)
        self.debug(f"Waiting {delay} seconds for next distribution.")
        await asyncio.sleep(delay)

        peers = list[Peer]()

        while len(peers) < self.params.distribution.minEligiblePeers:
            peers = await self.eligible_list.get()
            self.warning(
                f"Min. {self.params.distribution.minEligiblePeers} peers required to distribute rewards (having {len(peers)})."
            )
            await asyncio.sleep(2)

        # distribute rewards
        # randomly split peers into groups, one group per node
        self.info("Initiating distribution.")

        t: tuple[dict[str, dict[str, Any]], int] = await self.multiple_attempts_sending(
            peers, self.params.distribution.maxIterations
        )
        rewards, iterations = t  # trick for typehinting tuple unpacking
        self.info("Distribution completed.")

        self.debug(f"Rewards distributed in {iterations} iterations: {rewards}")

        try:
            with DatabaseConnection(self.params.pg) as session:
                entries = set[Reward]()

                for peer, values in rewards.items():
                    expected = values.get("expected", 0)
                    remaining = values.get("remaining", 0)
                    issued = values.get("issued", 0)
                    effective = expected - remaining
                    status = "SUCCESS" if remaining < 1 else "TIMEOUT"

                    entry = Reward(
                        peer_id=peer,
                        node_address="",
                        expected_count=expected,
                        effective_count=effective,
                        status=status,
                        timestamp=datetime.fromtimestamp(time.time()),
                        issued_count=issued,
                    )

                    entries.add(entry)

                session.add_all(entries)
                session.commit()

                self.debug(f"Stored {len(entries)} reward entries in database: {entry}")
        except Exception as err:
            self.error(f"Database error while storing distribution results: {err}")

        self.info(f"Distributed rewards to {len(peers)} peers.")

        EXECUTIONS_COUNTER.inc()

    async def multiple_attempts_sending(
        self, peers: list[Peer], max_iterations: int = 4
    ) -> dict[str, dict[str, Any]]:
        def _total_messages_to_send(rewards: dict[str, dict[str, int]]) -> int:
            return sum(
                [max(value.get("remaining", 0), 0) for value in rewards.values()]
            )

        iteration: int = 0

        reward_per_peer = {
            peer.address.id: {
                "expected": peer.message_count,
                "remaining": peer.message_count,
                "issued": 0,
                "tag": idx,
                "ticket-price": self.budget.ticket_price,
            }
            for idx, peer in enumerate(peers)
        }

        self.info(f"Rewards to distribute: {reward_per_peer}")

        while (
            iteration < max_iterations and _total_messages_to_send(reward_per_peer) > 0
        ):
            peers_groups = Utils.splitDict(reward_per_peer, len(self.nodes))

            # send rewards to peers
            tasks = set[asyncio.Task]()
            for node, peers_group in zip(self.nodes, peers_groups):
                tasks.add(asyncio.create_task(node.distribute_rewards(peers_group)))
            issued_counts: list[dict] = await asyncio.gather(*tasks)

            # wait for message delivery (if needed)
            self.debug(
                f"Waiting {self.params.distribution.messageDeliveryDelay} for message delivery"
            )
            await asyncio.sleep(self.params.distribution.messageDeliveryDelay)

            # check inboxes for relayed messages
            self.debug("Checking inboxes")
            tasks = set[asyncio.Task]()
            for node, peers_group in zip(self.nodes, peers_groups):
                tasks.add(asyncio.create_task(node.check_inbox(peers_group)))
            relayed_counts: list[dict] = await asyncio.gather(*tasks)

            # for every peer, substract the relayed count from the total count
            for peer in reward_per_peer:
                reward_per_peer[peer]["remaining"] -= sum(
                    [res.get(peer, 0) for res in relayed_counts]
                )
                reward_per_peer[peer]["issued"] += sum(
                    [res.get(peer, 0) for res in issued_counts]
                )

            self.debug(f"Iteration {iteration} completed.")

            iteration += 1

        return reward_per_peer, iteration

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

    @formalin("Getting ticket price")
    @connectguard
    async def get_ticket_price(self):
        """
        Gets the ticket price from the api and sets the ticket_price LockedVar. The ticket price is used in the economic model to calculate the number of messages to send to a peer.
        """
        price = await self.api.ticket_price()

        if price is None:
            self.warning("Ticket price not available.")
            return

        await self.ticket_price.set(price)
        self.debug(f"Ticket price: {price}")

        self.legacy_model.budget.ticket_price = price
        self.sigmoid_model.budget.ticket_price = price

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
            await node._retrieve_address()
            self.tasks.update(node.tasks())

        self.started = True

        self.tasks.add(asyncio.create_task(self.healthcheck()))
        self.tasks.add(asyncio.create_task(self.check_subgraph_urls()))
        self.tasks.add(asyncio.create_task(self.get_peers_rewards()))
        self.tasks.add(asyncio.create_task(self.get_ticket_price()))

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

        for node in self.nodes:
            node.started = False

        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()
