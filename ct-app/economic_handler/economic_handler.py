import asyncio

import aiohttp

from tools.decorator import connectguard, formalin
from tools.hopr_node import HOPRNode
from tools.utils import getlogger
from tools.db_connection import DatabaseConnection, NodePeerConnection

from sqlalchemy import func

from .utils_econhandler import (
    exclude_elements,
    compute_ct_prob,
    compute_rewards,
    merge_topology_database_subgraph,
    economic_model_from_file,
    allow_many_node_per_safe,
    save_expected_reward_csv,
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
        :returns: a new instance of the Economic Handler
        """

        self.tasks = set[asyncio.Task]()
        self.rpch_endpoint = rpch_endpoint
        self.subgraph_endpoint = subgraph_endpoint

        self.topology_links_with_balance = None
        self.database_metrics = {}
        self.subgraph_dict = None
        self.rpch_nodes = None
        self.ct_nodes = None

        super().__init__(url=url, key=key)

    @formalin(sleep=10 * 60)
    async def host_available(self):
        print(f"{self.connected=}")
        return self.connected

    @connectguard
    # @wakeupcall_from_file(folder="/assets", filename="parameters.json")
    @formalin("Running scheduler", sleep=10)
    async def scheduler(self):
        # merge unique_safe_peerId_links with database metrics and subgraph data

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

        eligible_peers = merge_topology_database_subgraph(
            self.topology_links_with_balance,
            self.database_metrics,
            self.subgraph_dict,
        )

        allow_many_node_per_safe(eligible_peers)
        exclude_elements(eligible_peers, self.rpch_nodes + self.ct_nodes)

        # computation of cover traffic probability
        equations, parameters, budget_parameters = economic_model_from_file()
        compute_ct_prob(eligible_peers, equations, parameters)

        # calculate expected rewards
        expected_rewards = compute_rewards(eligible_peers, budget_parameters)

        # output expected rewards as a csv file
        save_expected_reward_csv(expected_rewards)

        print(f"{eligible_peers=}")
        print(f"{expected_rewards=}")

    @connectguard
    @formalin(message="Getting subgraph data", sleep=60 * 5)
    async def get_topology_links_with_balance(self):
        """
        Returns a dictionary containing all unique
        source_peerId-source_address links including
        the aggregated balance of "Open" outgoing payment channels
        """
        self.topology_links_with_balance = (
            await self.api.get_unique_nodeAddress_peerId_aggbalance_links()
        )

    @formalin(message="Getting RPCh nodes list", sleep=60 * 5)
    async def blacklist_rpch_nodes(self):
        """
        Retrieves a list of RPCH node peer IDs from the specified API endpoint.
        :returns: A list of RPCH node peer IDs extracted from the response.
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
            log.exception("An error occurred while making the request")
        except OSError:
            log.exception("An error occurred while reading the response")
        except Exception:
            log.exception("An unexpected error occurred")
        else:
            if data and isinstance(data, list):
                self.rpch_nodes = [item["id"] for item in data if "id" in item]

    @formalin(message="Getting CT nodes list", sleep=60 * 5)
    async def blacklist_ct_nodes(self):
        """
        Retrieves a list of CT node based on the content of the database
        :returns: A list of CT node peer IDs.
        """

        with DatabaseConnection() as session:
            nodes = session.query(NodePeerConnection.node).distinct().all()

        self.ct_nodes = [node[0] for node in nodes]

    @formalin(message="Getting database metrics", sleep=60 * 5)
    async def get_database_metrics(self):
        """
        This function establishes a connection to the database using the provided
        connection details, retrieves the latest peer information from the database
        table, and returns the data as a dictionary.
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

        new_metric_dict = {}

        for row in last_added_rows:
            if row.peer_id not in new_metric_dict:
                new_metric_dict[row.peer_id] = {
                    "node_peerIds": [],
                    "latency_metrics": [],
                    "timestamp": row.timestamp,
                    "temp_order": [],
                }

            new_metric_dict[row.peer_id]["node_peerIds"].append(row.node)
            new_metric_dict[row.peer_id]["latency_metrics"].append(row.latency)
            new_metric_dict[row.peer_id]["temp_order"].append(row.priority)

        # sort node_addresses and latency based on temp_order
        for peer_id in new_metric_dict:
            order = new_metric_dict[peer_id]["temp_order"]
            addresses = new_metric_dict[peer_id]["node_peerIds"]
            latency = new_metric_dict[peer_id]["latency_metrics"]

            addresses = [x for _, x in sorted(zip(order, addresses))]
            latency = [x for _, x in sorted(zip(order, latency))]

            new_metric_dict[peer_id]["node_peerIds"] = addresses
            new_metric_dict[peer_id]["latency_metrics"] = latency

        # remove the temp order key from the dictionaries
        for peer_id in new_metric_dict:
            del new_metric_dict[peer_id]["temp_order"]

        # TODO: ADD LOCK
        self.database_metrics = new_metric_dict

    @formalin(message="Getting subgraph data", sleep=60 * 5)
    async def get_subgraph_data(self):
        """
        This function retrieves safe_address-node_address-balance links from the
        specified subgraph using pagination.
        :returns: dict: A dictionary with the node_address as the key, the safe_address
        and the wxHOPR balance as values.
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
                    log.exception("An error occurred while sending the request")
                    return "subgraph_data", {}
                except ValueError:
                    log.exception(
                        "An error occurred while parsing the response as JSON"
                    )
                    return "subgraph_data", {}
                except OSError:
                    log.exception("An error occurred while reading the response")
                    return "subgraph_data", {}
                except Exception:
                    log.exception("An unexpected error occurred")
                    return "subgraph_data", {}
                else:
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

        # TODO: ADD LOCK
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
        self.tasks.add(asyncio.create_task(self.connect(address="hopr")))
        self.tasks.add(asyncio.create_task(self.host_available()))
        self.tasks.add(asyncio.create_task(self.get_database_metrics()))
        self.tasks.add(asyncio.create_task(self.get_topology_links_with_balance()))
        self.tasks.add(asyncio.create_task(self.blacklist_rpch_nodes()))
        self.tasks.add(asyncio.create_task(self.blacklist_ct_nodes()))
        self.tasks.add(asyncio.create_task(self.get_subgraph_data()))
        self.tasks.add(asyncio.create_task(self.close_incoming_channels()))
        self.tasks.add(asyncio.create_task(self.scheduler()))

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
