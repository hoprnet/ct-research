import asyncio
import csv
import os
import time
import traceback
import random
import aiohttp
from celery import Celery

from assets.parameters_schema import schema as schema_name
from tools.decorator import connectguard, wakeupcall_from_file, wakeupcall, formalin
from tools.hopr_node import HOPRNode
from tools.db_connection import DatabaseConnection, NodePeerConnection
from tools.utils import getlogger, read_json_file, envvar

from sqlalchemy import func

log = getlogger()


class EconomicHandler(HOPRNode):
    def __init__(
        self,
        url: str,
        key: str,
        rpch_endpoint: str,
        subgraph_url: str,
        sc_address: str,
    ):
        """
        :param url: the url of the HOPR node
        :param key: the API key of the HOPR node
        :param rpch_endpoint: endpoint returning rpch entry and exit nodes
        :returns: a new instance of the Economic Handler
        """

        self.tasks = set[asyncio.Task]()
        self.rpch_endpoint = rpch_endpoint
        self.subgraph_url = subgraph_url
        self.sc_address = sc_address

        super().__init__(url=url, key=key)

        # self.api_key = key
        # self.url = url
        # self.peer_id = None

        # # access the functionality of the hoprd python api
        # self.api = HoprdAPIHelper(url=url, token=key)

        # self.started = False

    @wakeupcall(seconds=10)
    async def host_available(self):
        print(f"{self.connected=}")
        return self.connected

    @wakeupcall_from_file(folder="/assets", filename="parameters.json")
    @connectguard
    async def scheduler(self, test_staging=True):
        """
        Schedules the tasks of the EconomicHandler in two different modes
        :param: staging (bool): If True, it uses the data returned by the database
        and adds all the necessary data from the channel topology api call response
        as well as the subgraph simply to the metrics dictionary to allow for easy
        testing of the app in the staging environment. If False, data from the database
        are mocked. This mode is better suited to test locally using pluto.
        """
        if test_staging:
            tasks = set[asyncio.Task]()

            expected_order = [
                "params",
                "metricsDB",
            ]

            tasks.add(asyncio.create_task(self.read_parameters_and_equations()))
            tasks.add(asyncio.create_task(self.get_database_metrics()))

            await asyncio.sleep(0)

            finished, _ = await asyncio.wait(tasks)

            unordered_tasks = [task.result() for task in finished]

            # Sort the results as the expected order cannot be guaranteed.
            ordered_tasks = sorted(
                unordered_tasks, key=lambda x: expected_order.index(x[0])
            )

            parameters_equations_budget = ordered_tasks[0][1:]
            database_metrics = ordered_tasks[1][1]

            # Add random stake and a random safe address to the metrics database
            _, new_database_metrics = self.add_random_data_to_metrics(database_metrics)

            # Extract Parameters
            parameters, equations, budget_param = parameters_equations_budget

            # computation of cover traffic probability
            _, ct_prob_dict = self.compute_ct_prob(
                parameters,
                equations,
                new_database_metrics,
            )

            # calculate expected rewards
            _, expected_rewards = self.compute_expected_reward(
                ct_prob_dict, budget_param
            )

            # calculate number of jobs per peer for the celery queue
            _, job_distribution = self.compute_job_distribution(
                expected_rewards, budget_param
            )

            print(f"{job_distribution=}")

        else:
            tasks = set[asyncio.Task]()

            expected_order = [
                "unique_peer_safe_links",
                "params",
                "rpch",
                "subgraph_data",
            ]

            tasks.add(asyncio.create_task(self.get_unique_safe_peerId_links()))
            tasks.add(asyncio.create_task(self.read_parameters_and_equations()))
            tasks.add(
                asyncio.create_task(self.blacklist_rpch_nodes(self.rpch_endpoint))
            )
            """
            tasks.add(
                asyncio.create_task(
                    self.get_staking_participations(
                        subgraph_url=self.subgraph_url,
                        staking_season=self.sc_address,
                        pagination_skip_size=1000,  # Maximum entries per query allowed by TheGraph
                    )
                )
            )
            """
            await asyncio.sleep(0)

            finished, _ = await asyncio.wait(tasks)

            unordered_tasks = [task.result() for task in finished]

            # Sort the results as the expected order cannot be guaranteed.
            ordered_tasks = sorted(
                unordered_tasks, key=lambda x: expected_order.index(x[0])
            )

            unique_safe_peerId_links = ordered_tasks[0][1]
            print(unique_safe_peerId_links)
            parameters_equations_budget = ordered_tasks[1][1:]
            rpch_nodes_blacklist = ordered_tasks[2][1]
            # staking_participations = ordered_tasks[3][1]

            # helper functions that allow to test the code by inserting
            # the peerIDs of the pluto nodes (SUBJECT TO REMOVAL)
            pluto_keys_in_mockdb_data = self.replace_keys_in_mock_data(
                unique_safe_peerId_links
            )
            pluto_keys_in_mocksubraph_data = self.replace_keys_in_mock_data_subgraph(
                unique_safe_peerId_links
            )

            # merge unique_safe_peerId_links with database metrics and subgraph data
            _, metrics_dict = self.merge_topology_metricdb_subgraph(
                unique_safe_peerId_links,
                pluto_keys_in_mockdb_data,
                pluto_keys_in_mocksubraph_data,
            )
            # print(metrics_dict)

            # Exclude RPCh entry and exit nodes from the reward computation
            _, metrics_dict_excluding_rpch = self.block_rpch_nodes(
                rpch_nodes_blacklist, metrics_dict
            )

            # update the metrics dictionary to allow for 1 to many safe address peerID links
            _, one_to_many_safe_peerid_links = self.safe_address_split_stake(
                metrics_dict_excluding_rpch
            )
            # print(one_to_many_safe_peerid_links)

            # Extract Parameters
            parameters, equations, budget_param = parameters_equations_budget

            # computation of cover traffic probability
            _, ct_prob_dict = self.compute_ct_prob(
                parameters,
                equations,
                one_to_many_safe_peerid_links,
            )

            # calculate expected rewards
            _, expected_rewards = self.compute_expected_reward(
                ct_prob_dict, budget_param
            )

            # calculate number of jobs per peer for the celery queue
            _, job_distribution = self.compute_job_distribution(
                expected_rewards, budget_param
            )

            # output expected rewards as a csv file
            self.save_expected_reward_csv(expected_rewards)

            # print(f"{staking_participations}")
            print(f"{job_distribution=}")
            # print(f"{rpch_nodes_blacklist=}")

    async def get_unique_safe_peerId_links(self):
        """
        Returns a dictionary containing all unique
        source_peerId-source_address links
        """
        response = await self.api.unique_safe_peerId_links()

        return "unique_peer_safe_links", response

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

            metrics_dict = {}

            for row in last_added_rows:
                if row.peer_id not in metrics_dict:
                    metrics_dict[row.peer_id] = {
                        "node_addresses": [],
                        "latency_metrics": [],
                        "Timestamp": row.timestamp,
                        "order": [],
                    }
                metrics_dict[row.peer_id]["node_addresses"].append(row.node)
                metrics_dict[row.peer_id]["latency_metrics"].append(row.latency)
                metrics_dict[row.peer_id]["temp_order"].append(row.order)

            # sort node_addresses and latency based on temp_order
            for peer_id in metrics_dict:
                order = metrics_dict[peer_id]["temp_order"]
                addresses = metrics_dict[peer_id]["node_addresses"]
                latency = metrics_dict[peer_id]["latency_metrics"]

                addresses = [x for _, x in sorted(zip(order, addresses))]
                latency = [x for _, x in sorted(zip(order, latency))]

                metrics_dict[peer_id]["node_addresses"] = addresses
                metrics_dict[peer_id]["latency_metrics"] = latency

            # remove the temp order key from the dictionaries
            for peer_id in metrics_dict:
                del metrics_dict[peer_id]["temp_order"]

            return "metricsDB", metrics_dict

    def add_random_data_to_metrics(self, metrics_dict):
        """
        Adds random stake and safe address to the metrics dict to mock the
        information returned by the channel topology and subgraph.
        :param metrics_dict: The metrics dict retrieved from the database.
        :return: The updated metrics dict with stake and safe address.
        """
        for peer_id, data in metrics_dict.items():
            # Add a random number between 1 and 100 to the "stake" key
            stake = random.randint(1, 100)
            data["stake"] = stake
            data["splitted_stake"] = stake / 2
            data["safe_address_count"] = random.randint(1, 5)

            # Generate a random 5-letter lowercase combination for "safe_address"
            safe_address = "0x" + "".join(
                random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(5)
            )
            data["safe_address"] = safe_address

        return "new_metrics_dict", metrics_dict

    def mock_data_metrics_db(self):
        """
        Generates a mock metrics dictionary that mimics the metrics database output.
        :returns: a dictionary containing mock metrics data with peer IDs and network
        watcher IDs odered by a statistical measure computed on latency
        """
        metrics_dict = {
            "peer_id_1": {"netw": ["node_1", "node_3"]},
            "peer_id_2": {"netw": ["node_1", "node_2", "node_4"]},
            "peer_id_3": {"netw": ["node_2", "node_3", "node_4"]},
            "peer_id_4": {"netw": ["node_1", "node_2", "node_3"]},
            "peer_id_5": {"netw": ["node_1", "node_2", "node_3", "node_4"]},
        }
        return metrics_dict

    def mock_data_subgraph(self):
        """
        Generates a dictionary that mocks the metrics received form the subgraph.
        :returns: a dictionary containing the data with safe stake addresses as key
                  and stake as value.
        """
        subgraph_dict = {
            "safe_1": 10,
            "safe_2": 55,
            "safe_3": 23,
            "safe_4": 85,
            "safe_5": 62,
        }
        return subgraph_dict

    def replace_keys_in_mock_data(self, unique_peerId_address: dict):
        """
        Just a helper function that allows me to replace my invented peerID's
        with the peerId's from Pluto.
        This function will be deleted when working with the real data.
        [NO NEED TO CHECK CODING STYLE NOR EFFICIENCY OF THE FUNCTION]
        """
        metrics_dict = self.mock_data_metrics_db()
        channel_topology_keys = list(unique_peerId_address.keys())

        new_metrics_dict = {}
        for i, key in enumerate(metrics_dict.keys()):
            new_key = channel_topology_keys[i]
            new_metrics_dict[new_key] = metrics_dict[key]

        return new_metrics_dict

    def replace_keys_in_mock_data_subgraph(self, channel_topology_result):
        """
        Just a helper function that allows me to replace my invented safe_addresses
        with the safe addresses from Pluto.
        This function will be deleted when working with the real data.
        [NO NEED TO CHECK CODING STYLE NOR EFFICIENCY OF THE FUNCTION]
        """
        subgraph_dict = self.mock_data_subgraph()
        channel_topology_values = list(channel_topology_result.values())

        new_subgraph_dict = {}
        for i, data in enumerate(subgraph_dict.values()):
            new_key = channel_topology_values[i]
            new_subgraph_dict[new_key] = data

        return new_subgraph_dict

    async def read_parameters_and_equations(self, file_name: str = "parameters.json"):
        """
        Reads parameters and equations from a JSON file and validates it using a schema.
        :param: file_name (str): The name of the JSON file containing the parameters
        and equations. Defaults to "parameters.json".
        :returns: dicts: The first dictionary contains the model parameters, the second
        dictionary contains the equations, and the third dictionary
        contains the budget parameters.
        """
        script_directory = os.path.dirname(os.path.abspath(__file__))
        assets_directory = os.path.join(script_directory, "../assets")
        parameters_file_path = os.path.join(assets_directory, file_name)

        contents = await asyncio.to_thread(
            read_json_file, parameters_file_path, schema_name
        )
        return (
            "params",
            contents["parameters"],
            contents["equations"],
            contents["budget_param"],
        )

    async def blacklist_rpch_nodes(self, api_endpoint: str):
        """
        Retrieves a list of RPCH node peer IDs from the specified API endpoint.
        :param: api_endpoint (str): The URL endpoint to retrieve the data from.
        :returns: A list of RPCH node peer IDs extracted from the response.
        Notes:
        - The function sends a GET request to the provided `api_endpoint`.
        - Expects the response to be a JSON-encoded list of items.
        - Filters out items that do not have the 'id' field.
        - Logs errors and traceback in case of failures.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_endpoint) as response:
                    if response.status != 200:
                        log.error(f"Received error code: {response.status}")
                        return "rpch", []
                    data = await response.json()
        except aiohttp.ClientError:
            log.exception("An error occurred while making the request")
        except OSError:
            log.exception("An error occurred while reading the response")
        except Exception:
            log.exception("An unexpected error occurred")
        else:
            if not data or not isinstance(data, list):
                return "rpch", []

            rpch_node_peerID = [item["id"] for item in data if "id" in item]
            return "rpch", rpch_node_peerID

        return "rpch", []

    async def get_staking_participations(
        self,
        subgraph_url: str,
        staking_season: str,
        pagination_skip_size: int,
    ):
        """
        This function retrieves staking participation data from the specified
        staking_season smart contract deployed on gnosis chain using The Graph API.
        The function uses pagination to handle large result sets, allowing retrieval of
        all staking participation records incrementally.
        :param: subgraph_url (str): The url for accessing The Graph API.
        :param: staking_season (str): The sc address of a given staking season.
        :param: pagination_skip_size (int): The number of records per pagination step.
        :returns: Tuple[str, Dict[str, int]]: A tuple containing the result identifier
        and a dictionary with account IDs of stakers and the amount of staked tokens.
        """

        query = """
            query GetStakingParticipations($stakingSeason: String, $first: Int, $skip: Int) {
                stakingParticipations(first: $first, skip: $skip, where: { stakingSeason: $stakingSeason }) {
                    id
                    account {
                        id
                    }
                    stakingSeason {
                        id
                    }
                    actualLockedTokenAmount
                }
            }
        """
        url = subgraph_url
        variables = {
            "stakingSeason": staking_season,
            "first": pagination_skip_size,
            "skip": 0,
        }

        data = {"query": query, "variables": variables}  # noqa: F841
        subgraph_dict = {}
        staking_participations = []
        more_content_available = True

        while more_content_available:
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, json=data) as response:
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
                    staking_info = json_data["data"]["stakingParticipations"]

                    staking_participations.extend(staking_info)
                    variables[
                        "skip"
                    ] += pagination_skip_size  # Increment skip for next iter
                    more_content_available = len(staking_info) == pagination_skip_size

        for item in staking_participations:
            account_id = item["account"]["id"]
            subgraph_dict[account_id] = (
                int(item["actualLockedTokenAmount"]) / 1e18
            )  # 1e18: Decimal Precision of the HOPR token

        log.info("Subgraph data dictionary generated")
        return "subgraph_data", subgraph_dict

    def merge_topology_metricdb_subgraph(
        self,
        unique_peerId_address: dict,
        new_metrics_dict: dict,
        new_subgraph_dict: dict,
    ):
        """
        Merge metrics and subgraph data with the unique peer IDs - addresses link.
        :param: unique_peerId_address: A dict mapping peer IDs to safe addresses.
        :param: new_metrics_dict: A dict containing metrics with peer ID as the key.
        :param: new_subgraph_dict: A dict containing subgraph data with
                safe address as the key.
        :returns: A dict with peer ID as the key and the merged information.
        """
        merged_result = {}

        try:
            # Merge based on peer ID
            for peer_id, safe_address in unique_peerId_address.items():
                if peer_id in new_metrics_dict and safe_address in new_subgraph_dict:
                    merged_result[peer_id] = {
                        "safe_address": safe_address,
                        "node_addresses": new_metrics_dict[peer_id]["netw"],
                        "stake": new_subgraph_dict[safe_address],
                    }
        except Exception as e:
            log.error(f"Error occurred while merging: {e}")
            log.error(traceback.format_exc())
            return "merged_data", {}

        return "merged_data", merged_result

    def block_rpch_nodes(
        self, blacklist_rpch_nodes: list, merged_metrics_subgraph_topology: dict
    ):
        """
        Removes RPCh entry and exit nodes from the dictioanry that
        contains the merged results of database metrics, subgraph, and topology.
        :param: blacklist_rpch_nodes (list): Containing a list of RPCh nodes
        :param: merged_metrics_subgraph_topology (dict): merged data
        :returns: (dict): Updated merged_metrics_subgraph_topology dataset
        """
        merged_metrics_subgraph_topology = {
            k: v
            for k, v in merged_metrics_subgraph_topology.items()
            if k not in blacklist_rpch_nodes
        }
        return "dict_excluding_rpch_nodes", merged_metrics_subgraph_topology

    def safe_address_split_stake(self, input_dict: dict):
        """
        Split the stake managed by a safe address equaly between the nodes
        that the safe manages.
        :param: input_dict: dictionary containing peerID, safeAdress and stake.
        :returns: updated dictionary with the splitted stake and the node counts
        """
        safe_address_counts = {}

        # Calculate the number of safe_addresses by peer_id
        for value in input_dict.values():
            safe_address = value["safe_address"]

            if safe_address not in safe_address_counts:
                safe_address_counts[safe_address] = 0

            safe_address_counts[safe_address] += 1

        # Update the input_dict with the calculated splitted_stake
        for value in input_dict.values():
            safe_address = value["safe_address"]
            stake = value["stake"]
            value["safe_address_count"] = safe_address_counts[safe_address]

            value["splitted_stake"] = stake / value["safe_address_count"]

        return "split_stake_dict", input_dict

    def compute_ct_prob(self, parameters, equations, merged_result):
        """
        Evaluate the function for each stake value in the merged_result dictionary.
        :param: parameters: A dict containing the parameter values.
        :param: equations: A dict containing the equations and conditions.
        :param: A dict containing the data.
        :returns: A dict containing the probability distribution.
        """
        results = {}
        f_x_condition = equations["f_x"]["condition"]

        # compute transformed stake
        for key, value in merged_result.items():
            stake = value["splitted_stake"]
            params = {param: value["value"] for param, value in parameters.items()}
            params["x"] = stake

            try:
                if eval(f_x_condition, params):
                    function = "f_x"
                else:
                    function = "g_x"

                formula = equations[function]["formula"]
                result = eval(formula, params)
                results[key] = {"trans_stake": result}

            except Exception as e:
                log.error(f"Error evaluating function for peer ID {key}: {e}")
                log.error(traceback.format_exc())
                return "ct_prob", {}

        # compute ct probability
        sum_values = sum(result["trans_stake"] for result in results.values())
        for key in results:
            results[key]["prob"] = results[key]["trans_stake"] / sum_values

        # update dictionary with model results
        for key in merged_result:
            if key in results:
                merged_result[key].update(results[key])

        return "ct_prob", merged_result

    def compute_expected_reward(self, dataset: dict, budget_param: dict):
        """
        Computes the expected reward for each entry in the dataset.
        :param: dataset (dict): A dictionary containing the dataset entries.
        :param: budget (dict): A dictionary containing the budget information.
        :returns: dict: The updated dataset with the 'expected_reward' value
        and reward splits for the automatic and airdrop mode.
        """
        budget = budget_param["budget"]["value"]
        budget_split_ratio = budget_param["s"]["value"]
        dist_freq = budget_param["dist_freq"]["value"]

        for entry in dataset.values():
            entry["budget"] = budget
            entry["budget_split_ratio"] = budget_split_ratio
            entry["distribution_frequency"] = dist_freq

            total_exp_reward = entry["prob"] * budget
            protocol_exp_reward = total_exp_reward * budget_split_ratio

            entry["total_expected_reward"] = total_exp_reward
            entry["airdrop_expected_reward"] = total_exp_reward * (
                1 - budget_split_ratio
            )
            entry["protocol_exp_reward"] = protocol_exp_reward

            entry["protocol_exp_reward_per_dist"] = protocol_exp_reward / dist_freq

        return "expected_reward", dataset

    def compute_job_distribution(self, dataset: dict, budget_param: dict):
        """
        Computes the number of jobs that must be executed per peer to satisfy the
        protocol reward for each distribution in expectation.
        :param: dataset (dict): A dictionary containing the expected reward.
        :param: budget (dict): A dictionary containing the budget information.
        :returns: dict: The updated dataset with the 'jobs' value determining the
        amount of tasks to be sent.
        """
        ticket_price = budget_param["ticket_price"]["value"]
        winning_prob = budget_param["winning_prob"]["value"]
        denominator = ticket_price * winning_prob

        for entry in dataset.values():
            entry["ticket_price"] = ticket_price
            entry["winning_prob"] = winning_prob
            entry["ticket_price_times_winning_prob"] = denominator

            entry["jobs"] = round(entry["protocol_exp_reward_per_dist"] / denominator)

        return "job_distribution", dataset

    def save_expected_reward_csv(self, dataset: dict) -> bool:
        """
        Saves the expected rewards dictionary as a CSV file
        :param: dataset (dict): A dictionary containing the dataset entries.
        :returns: bool: No meaning except that it allows testing of the function.
        """
        timestamp = time.strftime("%Y%m%d%H%M%S")
        folder_name = "expected_rewards"
        folder_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), folder_name
        )
        filename = f"expected_reward_{timestamp}.csv"
        file_path = os.path.join(folder_path, filename)

        try:
            os.makedirs(folder_path, exist_ok=True)
        except OSError as e:
            log.error(f"Error occurred while creating the folder: {e}")
            log.error(traceback.format_exc())
            return False

        try:
            with open(file_path, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                column_names = list(dataset.values())[0].keys()
                writer.writerow(["peer_id"] + list(column_names))
                for key, value in dataset.items():
                    writer.writerow([key] + list(value.values()))
        except OSError as e:
            log.error(f"Error occurred while writing to the CSV file: {e}")
            log.error(traceback.format_exc())
            return False

        log.info("CSV file saved successfully")
        return True

    def push_jobs_to_celery_queue(self, dataset: dict):
        """
        Sends jobs to the celery queue including the number of jobs and an ordered
        list of postmans that execute the jobs.
        :param: dataset (dict): Contains the job number and postman list by peer id.
        :returns: nothing.
        """
        app = Celery(
            name="client",
            broker=envvar("CELERY_BROKER_URL"),
            backend=envvar("CELERY_RESULT_BACKEND"),
            include=["celery_tasks"],
        )
        app.autodiscover_tasks(force=True)

        for peer_id, value in dataset.items():
            node_list = value["node_addresses"]
            count = value["jobs"]
            node_index = 0

            app.send_task(
                f"{envvar('TASK_NAME')}.{node_list[node_index]}",
                args=(peer_id, count, node_list, node_index),
                queue=node_list[node_index],
            )

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
        self.tasks.add(asyncio.create_task(self.scheduler()))
        self.tasks.add(asyncio.create_task(self.close_incoming_channels())

        await asyncio.gather(*self.tasks)

    ################## MOCKING FOR TESTING DEPLOYMENT ##################
    async def mockstart(self):
        """
        Starts the tasks of this node
        """
        log.debug("Running EconomicHandler instance")

        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.fake_method()))

        await asyncio.gather(*self.tasks)

    @wakeupcall("Entering fake method", seconds=15)
    async def fake_method(self):
        log.info("Fake log from the fake method")

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
