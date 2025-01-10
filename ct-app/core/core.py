# region Imports
import asyncio
import random

from prometheus_client import Gauge

from .api import HoprdAPI
from .baseclass import Base
from .components import Address, AsyncLoop, LockedVar, Parameters, Peer, Utils
from .components.decorators import flagguard, formalin
from .economic_model import EconomicModelTypes
from .node import Node
from .subgraph import URL, ProviderError, Type, entries

# endregion

# region Metrics
PEER_VERSION = Gauge("ct_peer_version", "Peer version", ["peer_id", "version"])
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")
ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", [
        "peer_id", "model"]
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

        self.tasks = set[asyncio.Task]()

        self.all_peers = LockedVar("all_peers", set[Peer]())
        self.topology_data = list[entries.Topology]()
        self.registered_nodes_data = list[entries.Node]()
        self.nft_holders_data = list[str]()
        self.allocations_data = list[entries.Allocation]()
        self.eoa_balances_data = list[entries.Balance]()
        self.peers_rewards_data = dict[str, float]()

        self.models = {
            m: m.model.fromParameters(
                getattr(self.params.economicModel, m.value))
            for m in EconomicModelTypes
        }

        self.providers = {
            s: s.provider(URL(self.params.subgraph, s.value)) for s in Type
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
        Checks the subgraph URLs and sets the subgraph mode in use (default, backup or none).
        """
        for provider in self.providers.values():
            await provider.test(self.params.subgraph.type)

    @flagguard
    @formalin
    async def connected_peers(self):
        """
        Aggregates the peers from all nodes and sets the all_peers LockedVar.
        """

        counts = {"new": 0, "known": 0, "unreachable": 0}

        async with self.all_peers as current_peers:
            visible_peers: set[Peer] = set()
            visible_peers.update(*[await node.peers.get() for node in self.nodes])
            visible_peers = list(visible_peers)

            for peer in current_peers:
                # if peer is still visible
                if peer in visible_peers:
                    if peer.yearly_message_count is None:
                        peer.yearly_message_count = 0
                        peer.start_async_processes()
                    counts["known"] += 1

                    # update peer version if it has been succesfully retrieved
                    new_version = visible_peers[visible_peers.index(
                        peer)].version
                    if new_version.major != 0:
                        peer.version = new_version

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

            for peer in current_peers:
                PEER_VERSION.labels(peer.address.hopr,
                                    str(peer.version)).set(1)

    @flagguard
    @formalin
    async def registered_nodes(self):
        """
        Gets all registered nodes in the Network Registry.
        """

        results = list[entries.Node]()
        try:
            for safe in await self.providers[Type.SAFES].get():
                results.extend(
                    [
                        entries.Node.fromSubgraphResult(node)
                        for node in safe["registeredNodesInNetworkRegistry"]
                    ]
                )

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
            for nft in await self.providers[Type.STAKING].get():
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
        results = list[entries.Allocation]()
        try:
            for account in await self.providers[Type.MAINNET_ALLOCATIONS].get():
                results.append(entries.Allocation(**account["account"]))
        except ProviderError as err:
            self.error(f"allocations: {err}")

        try:
            for account in await self.providers[Type.GNOSIS_ALLOCATIONS].get():
                results.append(entries.Allocation(**account["account"]))
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
            for account in await self.providers[Type.MAINNET_BALANCES].get(
                id_in=list(balances.keys())
            ):
                balances[account["id"]
                         ] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        try:
            for account in await self.providers[Type.GNOSIS_BALANCES].get(
                id_in=list(balances.keys())
            ):
                balances[account["id"]
                         ] += float(account["totalBalance"]) / 1e18
        except ProviderError as err:
            self.error(f"eoa_balances: {err}")

        self.eoa_balances_data = [
            entries.Balance(key, value) for key, value in balances.items()
        ]
        self.debug(f"Fetched EOA balances ({len(balances)} entries).")

    @flagguard
    @formalin
    async def topology(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """

        channels = self.channels
        if channels is None or channels.all is None:
            self.warning("Topology data not available")
            return

        self.topology_data = [
            entries.Topology.fromDict(*arg)
            for arg in (await Utils.balanceInChannels(channels.all)).items()
        ]

        TOPOLOGY_SIZE.set(len(self.topology_data))
        self.debug(
            f"Fetched topology links ({len(self.topology_data)} entries).")

    @flagguard
    @formalin
    async def apply_economic_model(self):
        """
        Applies the economic model to the eligible peers (after multiple filtering layers).
        """
        async with self.all_peers as peers:
            if not all(
                [len(self.topology_data), len(
                    self.registered_nodes_data), len(peers)]
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

            Utils.allowManyNodePerSafe(peers)

            for p in peers:
                if not p.is_eligible(
                    self.params.economicModel.minSafeAllowance,
                    self.models[EconomicModelTypes.LEGACY].coefficients.l,
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

            model_input = {
                EconomicModelTypes.LEGACY: 0,
                EconomicModelTypes.SIGMOID: [economic_security, network_capacity],
            }
            message_count = {
                EconomicModelTypes.LEGACY: 0,
                EconomicModelTypes.SIGMOID: 0,
            }
            for peer in peers:
                if peer.yearly_message_count is None:
                    continue

                model_input[EconomicModelTypes.LEGACY] = self.peers_rewards_data.get(
                    peer.address.native, 0.0
                )

                for model in self.models:
                    message_count[model] = self.models[model].yearly_message_count(
                        peer.split_stake,
                        model_input[model],
                    )

                    MESSAGE_COUNT.labels(peer.address.hopr, model.name).set(
                        message_count[model]
                    )

                peer.yearly_message_count = sum(message_count.values())

            eligibles = sum(
                [p.yearly_message_count is not None for p in peers])
            self.info(f"Eligible nodes: {eligibles} entries.")
            ELIGIBLE_PEERS.set(eligibles)

    @flagguard
    @formalin
    async def peers_rewards(self):
        results = dict()
        try:
            for account in await self.providers[Type.REWARDS].get():
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
        ticket_price = await self.api.ticket_price()
        if ticket_price is None:
            self.warning("Ticket price not available.")
            return

        win_probability = await self.api.winning_probability()
        if win_probability is None:
            self.warning("Winning probability not available.")
            return

        self.debug(
            f"Ticket price: {ticket_price.value}, winning probability: {win_probability.value}"
        )

        for model in self.models.values():
            model.budget.ticket_price = ticket_price.value
            model.budget.winning_probability = win_probability.value

    @flagguard
    @formalin
    async def safe_fundings(self):
        """
        Gets the total amount that was sent to CT safes.
        """
        provider = self.providers[Type.FUNDINGS]

        addresses = list(
            filter(
                lambda x: x is not None,
                {await node.safe_address for node in self.nodes},
            )
        )

        try:
            entries = await provider.get(to_in=addresses)
        except ProviderError as err:
            self.error(f"get_peers_rewards: {err}")
            entries = []
        amount = sum([float(item["amount"]) for item in entries])

        TOTAL_FUNDING.set(amount + self.params.fundings.constant)
        self.debug(
            f"Fetched safe fundings ({amount} + {self.params.fundings.constant})"
        )

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
            AsyncLoop.add(node.observe_message_queue)

        await AsyncLoop.gather()

    def stop(self):
        """
        Stop the node.
        """
        self.info("CTCore stopped.")
        self.running = False
