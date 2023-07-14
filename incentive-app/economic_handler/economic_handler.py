import logging
import os
import traceback
import json
import jsonschema
import csv
import time
import asyncio
import aiohttp

from tools.hopr_node import HOPRNode
from .parameters_schema import schema

from tools.decorator import wakeupcall, connectguard

log = logging.getLogger(__name__)


class EconomicHandler(HOPRNode):
    def __init__(self, url: str, key: str, rpch_endpoint: str):
        """
        :param url: the url of the HOPR node
        :param key: the API key of the HOPR node
        :param rpch_endpoint: endpoint returning rpch entry and exit nodes
        :returns: a new instance of the Economic Handler
        """

        self.tasks = set[asyncio.Task]()
        self.rpch_endpoint = rpch_endpoint

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

    @wakeupcall(seconds=15)
    @connectguard
    async def scheduler(self):
        """
        Schedules the tasks of the EconomicHandler
        """
        tasks = set[asyncio.Task]()

        expected_order = ["unique_peer_safe_links", "params", "rpch"]

        tasks.add(asyncio.create_task(self.get_unique_safe_peerId_links()))
        tasks.add(asyncio.create_task(self.read_parameters_and_equations()))
        tasks.add(asyncio.create_task(self.blacklist_rpch_nodes(self.rpch_endpoint)))

        await asyncio.sleep(0)

        finished, _ = await asyncio.wait(tasks)

        unordered_tasks = [task.result() for task in finished]

        # sort the results according to the expected order.
        # This is necessary because the order of the results is not guaranteed.
        ordered_tasks = sorted(
            unordered_tasks, key=lambda x: expected_order.index(x[0])
        )

        unique_safe_peerId_links = ordered_tasks[0][1]
        parameters_equations_budget = ordered_tasks[1][1:]
        rpch_nodes_blacklist = ordered_tasks[2][1]

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

        # Extract Parameters
        parameters, equations, budget = parameters_equations_budget

        # computation of cover traffic probability
        _, ct_prob_dict = self.compute_ct_prob(
            parameters,
            equations,
            metrics_dict,
        )

        # calculate expected rewards
        _, expected_rewards = self.compute_expected_reward(ct_prob_dict, budget)

        # output expected rewards as a csv file
        self.save_expected_reward_csv(expected_rewards)

        print(f"{expected_rewards=}")
        print(f"{rpch_nodes_blacklist=}")

    async def get_unique_safe_peerId_links(self):
        """
        Returns a dictionary containing all unique
        source_peerId-source_address links
        """
        response = await self.api.get_unique_safe_peerId_links()

        return "unique_peer_safe_links", response

    def mock_data_metrics_db(self):
        """
        Generates a mock metrics dictionary that mimics the metrics database output.
        :returns: a dictionary containing mock metrics data with peer IDs and network
        watcher IDs odered by a statistical measure computed on latency
        """
        metrics_dict = {
            "peer_id_1": {"netw": ["nw_1", "nw_3"]},
            "peer_id_2": {"netw": ["nw_1", "nw_2", "nw_4"]},
            "peer_id_3": {"netw": ["nw_2", "nw_3", "nw_4"]},
            "peer_id_4": {"netw": ["nw_1", "nw_2", "nw_3"]},
            "peer_id_5": {"netw": ["nw_1", "nw_2", "nw_3", "nw_4"]},
        }
        return metrics_dict

    def mock_data_subgraph(self):
        """
        Generates a dictionary that mocks the metrics received form the subgraph.
        :returns: a dictionary containing the data with safe stake addresses as key
                  and stake as value.
        """
        subgraph_dict = {
            "safe_1": {"stake": 10},
            "safe_2": {"stake": 55},
            "safe_3": {"stake": 23},
            "safe_4": {"stake": 85},
            "safe_5": {"stake": 62},
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
        :returns: dicts: The first dictionary contains the parameters, the second
        dictionary contains the equations, and the third dictionary the budget.
        """
        script_directory = os.path.dirname(os.path.abspath(__file__))
        parameters_file_path = os.path.join(script_directory, file_name)

        try:
            with open(parameters_file_path, "r") as file:
                contents = await asyncio.to_thread(json.load, file)
        except FileNotFoundError as e:
            log.error(f"The file '{file_name}' does not exist. {e}")
            log.error(traceback.format_exc())
            return "params", {}, {}, {}

        parameters = contents.get("parameters", {})
        equations = contents.get("equations", {})
        budget = contents.get("budget", {})

        try:
            jsonschema.validate(
                instance={
                    "parameters": parameters,
                    "equations": equations,
                    "budget": budget,
                },
                schema=schema,
            )
        except jsonschema.ValidationError as e:
            log.error(
                f"The file '{file_name}' does not follow the expected structure. {e}"
            )
            log.error(traceback.format_exc())
            return "params", {}, {}, {}

        return "params", parameters, equations, budget

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
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list) and data:
                            rpch_node_peerID = [
                                item["id"] for item in data if "id" in item
                            ]
                            return "rpch", rpch_node_peerID
                    else:
                        log.error(f"Received error code: {response.status}")
        except aiohttp.ClientError as e:
            log.error(f"An error occurred while making the request: {e}")
            log.error(traceback.format_exc())
        except ValueError as e:
            log.error(f"An error occurred while parsing the response as JSON: {e}")
            log.error(traceback.format_exc())
        except Exception as e:
            log.error(f"An unexpected error occurred: {e}")
            log.error(traceback.format_exc())

        return "rpch", []

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
                        "netwatchers": new_metrics_dict[peer_id]["netw"],
                        "stake": new_subgraph_dict[safe_address]["stake"],
                    }
        except Exception as e:
            log.error(f"Error occurred while merging: {e}")
            log.error(traceback.format_exc())
            return "merged_data", {}

        return "merged_data", merged_result

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
            stake = value["stake"]
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

    def compute_expected_reward(self, dataset: dict, budget: dict):
        """
        Computes the expected reward for each entry in the dataset.
        :param: dataset (dict): A dictionary containing the dataset entries.
        :param: budget (dict): A dictionary containing the budget information.
        :returns: dict: The updated dataset with the 'expected_reward' value.
        """
        for entry in dataset.values():
            entry["budget"] = budget["value"]
            entry["expected_reward"] = entry["prob"] * budget["value"]

        return "expected_reward", dataset

    def save_expected_reward_csv(self, dataset: dict) -> str:
        """
        Saves the expected rewards dictionary as a CSV file
        :param: dataset (dict): A dictionary containing the dataset entries.
        :returns: str: Confirmation message of successfull dataset save.
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
            return "expected_rewards_csv", {}

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
            return "expected_reward_csv", {}

        log.info("CSV file saved successfully")
        return "CSV file saved successfully"

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

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this node
        """
        log.debug("Stopping EconomicHandler instance")

        self.started = False
        for task in self.tasks:
            task.cancel()
        self.tasks = set()
