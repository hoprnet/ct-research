import asyncio
import aiohttp
from copy import deepcopy

from tools.decorator import connectguard, formalin, wakeupcall_from_file  # noqa: F401
from tools.hopr_node import HOPRNode
from tools.utils import getlogger
from tools.db_connection import DatabaseConnection, NodePeerConnection

from sqlalchemy import func

from .utils_econhandler import (
    exclude_elements,
    reward_probability,
    compute_rewards,
    merge_topology_database_subgraph,
    economic_model_from_file,
    allow_many_node_per_safe,
)

log = getlogger()


class EconomicHandler(HOPRNode):
    def __init__(
        self,
        url: str,
        key: str,
        rpch_endpoint: str,
        subgraph_endpoint: str,
    ):
        """
        :param url: the url of the HOPR node
        :param key: the API key of the HOPR node
        :param rpch_endpoint: endpoint returning rpch entry and exit nodes
        """

        self.tasks = set[asyncio.Task]()
        self.rpch_endpoint = rpch_endpoint
        self.subgraph_endpoint = subgraph_endpoint

        self.topology_links_with_balance = None
        self.database_metrics = {}
        self.subgraph_dict = None
        self.rpch_nodes = None
        self.ct_nodes = None

        self.topology_lock = asyncio.Lock()
        self.database_lock = asyncio.Lock()
        self.subgraph_lock = asyncio.Lock()
        self.rpch_node_lock = asyncio.Lock()
        self.ct_node_lock = asyncio.Lock()

        super().__init__(url=url, key=key)

    @formalin(sleep=10 * 60)
    async def host_available(self):
        print(f"{self.connected=}")
        return self.connected

    @connectguard
    @wakeupcall_from_file(folder="assets", filename="parameters.json")
    # @formalin("Running the economic model", sleep=10)
    async def apply_economic_model(self):
        # merge unique_safe_peerId_links with database metrics and subgraph data

        # TODO add while loop
        if not self.topology_links_with_balance:
            log.warning("No topology data available for scheduler")
            return
        if len(self.database_metrics) == 0:
            log.warning("No database metrics available for scheduler")
            return
        if not self.subgraph_dict:
            log.warning("No subgraph data available for scheduler")
            return
        if not self.rpch_nodes:
            log.warning("No RPCh nodes available for scheduler")
            return
        if not self.ct_nodes:
            log.warning("No CT nodes available for scheduler")
            return

        # if missing_informations:
        #     await asyncio.sleep(5)
        #     continue

        # missing_informations = False

        # wait for topolofy, database, and subgraph locks to be released
        async with self.topology_lock:
            local_topology = deepcopy(self.topology_links_with_balance)
        async with self.database_lock:
            local_database = deepcopy(self.database_metrics)
        async with self.subgraph_lock:
            local_subgraph = deepcopy(self.subgraph_dict)
        async with self.rpch_node_lock:
            local_rpch = deepcopy(self.rpch_nodes)
        async with self.ct_node_lock:
            local_ct = deepcopy(self.ct_nodes)

        eligible_peers = merge_topology_database_subgraph(
            local_topology,
            local_database,
            local_subgraph,
        )

        allow_many_node_per_safe(eligible_peers)
        exclude_elements(eligible_peers, local_rpch + local_ct)

        # computation of cover traffic probability
        equations, parameters, budget_parameters = economic_model_from_file()
        reward_probability(eligible_peers, equations, parameters)

        # calculate expected rewards
        compute_rewards(eligible_peers, budget_parameters)

        # output expected rewards as a csv file

        if len(eligible_peers) == 0:
            log.warning(
                "No peers seams to be eligeable for rewards. Skipping distribution"
            )
            return

        # save_dict_to_csv(
        #     eligible_peers, "expected_reward", foldername="expected_rewards"
        # )

        # print(f"{eligible_peers=}")
        # print(f"{expected_rewards=}")

    @connectguard
    @formalin(message="Getting subgraph data", sleep=60 * 5)
    async def get_topology_links_with_balance(self):
        """
        Gets a dictionary containing all unique source_peerId-source_address links
        including the aggregated balance of "Open" outgoing payment channels.
        """
        topology = await self.api.get_unique_nodeAddress_peerId_aggbalance_links()

        async with self.topology_lock:
            self.topology_links_with_balance = topology
        log.info("Fetched unique nodeAddress-peerId links from topology.")
        log.debug(f"Unique nodeAddress-peerId links: {topology}")

    @formalin(message="Getting RPCh nodes list", sleep=60 * 5)
    async def get_rpch_nodes(self):
        """
        Retrieves a list of RPCH node peer IDs from the specified API endpoint.
        Notes:
        - The function sends a GET request to the provided `api_endpoint`.
        - Expects the response to be a JSON-encoded list of items.
        - Filters out items that do not have the 'id' field.
        - Logs errors and traceback in case of failures.
        """

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.rpch_endpoint) as response:
                    if response.status != 200:
                        log.error(f"Received error code: {response.status}")
                        return
                    data = await response.json()
        except aiohttp.ClientError:
            log.exception("An error occurred while making the request to rpch endpoint")
            return
        except OSError:
            log.exception(
                "An error occurred while reading the response from rpch endpoint"
            )
            return
        except Exception:
            log.exception(
                "An unexpected error occurred while making the request rpch endpoint"
            )
            return

        if data and isinstance(data, list):
            async with self.rpch_node_lock:
                self.rpch_nodes = [item["id"] for item in data if "id" in item]

        log.info(f"Fetched list of {len(self.rpch_nodes)} RPCh nodes.")
        log.debug(f"RPCh nodes: {self.rpch_nodes}")

    @formalin(message="Getting CT nodes list", sleep=60 * 5)
    async def get_ct_nodes(self):
        """
        Retrieves a list of CT node based on the content of the database
        """
        with DatabaseConnection() as session:
            nodes = session.query(NodePeerConnection.node).distinct().all()

        async with self.ct_node_lock:
            self.ct_nodes = [node[0] for node in nodes]
        log.info(f"Fetched list of {len(nodes)} CT nodes.")
        log.debug(f"CT nodes: {self.ct_nodes}")

    @formalin(message="Getting database metrics", sleep=60 * 5)
    async def get_database_metrics(self):
        """
        This function establishes a connection to the database using the provided
        connection details, retrieves the latest peer information from the database
        table.
        """
        with DatabaseConnection() as session:
            max_timestamp = session.query(
                func.max(NodePeerConnection.timestamp)
            ).scalar()

            last_added_rows = (
                session.query(NodePeerConnection)
                .filter_by(timestamp=max_timestamp)
                .all()
            )

        metric_dict = {}

        for row in last_added_rows:
            if row.peer_id not in metric_dict:
                metric_dict[row.peer_id] = {
                    "node_peer_ids": [],
                    "latency_metrics": [],
                    "timestamp": row.timestamp,
                    "temp_order": [],
                }

            metric_dict[row.peer_id]["node_peer_ids"].append(row.node)
            metric_dict[row.peer_id]["latency_metrics"].append(row.latency)
            metric_dict[row.peer_id]["temp_order"].append(row.priority)

        # sort node_peer_ids and latency based on temp_order
        for peer_id in metric_dict:
            order = metric_dict[peer_id]["temp_order"]
            node_peer_ids = metric_dict[peer_id]["node_peer_ids"]
            latency = metric_dict[peer_id]["latency_metrics"]

            node_peer_ids = [x for _, x in sorted(zip(order, node_peer_ids))]
            latency = [x for _, x in sorted(zip(order, latency))]

            metric_dict[peer_id]["node_peer_ids"] = node_peer_ids
            metric_dict[peer_id]["latency_metrics"] = latency

        # remove the temp order key from the dictionaries
        for peer_id in metric_dict:
            del metric_dict[peer_id]["temp_order"]

        async with self.database_lock:
            self.database_metrics = metric_dict

        log.info("Fetched data from database.")
        log.debug(f"Database entries: {metric_dict}")

    @formalin(message="Getting subgraph data", sleep=60 * 5)
    async def get_subgraph_data(self):
        """
        This function retrieves safe_address-node_address-balance links from the
        specified subgraph using pagination.
        """

        query = """
            query SafeNodeBalance($first: Int, $skip: Int) {
                safes(first: $first, skip: $skip) {
                    registeredNodesInNetworkRegistry {
                    node {
                        id
                    }
                    safe {
                        id
                        balance {
                        wxHoprBalance
                        }
                    }
                    }
                    registeredNodesInSafeRegistry {
                    node {
                        id
                    }
                    safe {
                        id
                        balance {
                        wxHoprBalance
                        }
                    }
                    }
                }
            }
        """

        data = {
            "query": query,
            "variables": {
                "first": 1000,
                "skip": 0,
            },
        }
        subgraph_dict = {}
        more_content_available = True
        pagination_skip_size = 1000

        while more_content_available:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        self.subgraph_endpoint, json=data
                    ) as response:
                        if response.status != 200:
                            log.error(
                                f"Received status code {response.status} when",
                                "querying The Graph API",
                            )
                            break

                        json_data = await response.json()

                except aiohttp.ClientError:
                    log.exception(
                        "An error occurred while sending the request to "
                        + "subgraph endpoint"
                    )
                    return
                except ValueError:
                    log.exception(
                        "An error occurred while parsing the response as JSON from "
                        + "subgraph endpoint"
                    )
                    return
                except OSError:
                    log.exception("An error occurred while reading the response")
                    return
                except Exception:
                    log.exception("An unexpected error occurred")
                    return

                safes = json_data["data"]["safes"]
                for safe in safes:
                    for node in (
                        safe["registeredNodesInNetworkRegistry"]
                        + safe["registeredNodesInSafeRegistry"]
                    ):
                        node_address = node["node"]["id"]
                        wxHoprBalance = node["safe"]["balance"]["wxHoprBalance"]
                        safe_address = node["safe"]["id"]
                        subgraph_dict[node_address] = {
                            "safe_address": safe_address,
                            "wxHOPR_balance": wxHoprBalance,
                        }

                # Increment skip for next iteration
                data["variables"]["skip"] += pagination_skip_size
                more_content_available = len(safes) == pagination_skip_size

        log.info("Subgraph data dictionary generated")

        async with self.subgraph_lock:
            self.subgraph_dict = subgraph_dict

    @formalin(message="Closing incoming channels", sleep=60 * 5)
    @connectguard
    async def close_incoming_channels(self):
        """
        Closes all incoming channels.
        """

        incoming_channels_ids = await self.api.incoming_channels(only_id=True)

        for channel_id in incoming_channels_ids:
            await self.api.close_channel(channel_id)

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.debug("Running EconomicHandler instance")

        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.connect()))
        self.tasks.add(asyncio.create_task(self.host_available()))
        self.tasks.add(asyncio.create_task(self.get_database_metrics()))
        self.tasks.add(asyncio.create_task(self.get_topology_links_with_balance()))
        self.tasks.add(asyncio.create_task(self.get_rpch_nodes()))
        self.tasks.add(asyncio.create_task(self.get_ct_nodes()))
        self.tasks.add(asyncio.create_task(self.get_subgraph_data()))
        self.tasks.add(asyncio.create_task(self.close_incoming_channels()))
        self.tasks.add(asyncio.create_task(self.apply_economic_model()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this node
        """
        log.debug("Stopping EconomicHandler instance")

        self.started = False
        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()

        self.tasks = set()
