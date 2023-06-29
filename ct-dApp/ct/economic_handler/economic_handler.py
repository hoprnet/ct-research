import logging
import os
import traceback
import json
import jsonschema
import requests
import csv
import time
import asyncio
import aiohttp

from ct.hopr_api_helper import HoprdAPIHelper
from .parameters_schema import schema

# Configure logging to output log messages to the console
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class EconomicHandler():
    def __init__(self, url: str, key: str):
        """
        :param url: the url of the HOPR node
        :param key: the API key of the HOPR node
        :returns: a new instance of the Economic Handler using 'url' and API 'key'
        """
        self.api_key = key
        self.url = url
        self.peer_id = None

        # access the functionality of the hoprd python api
        self.api = HoprdAPIHelper(url=url, token=key)

        self.started = False
        log.debug("Created EconomicHandler instance")

    async def channel_topology(self, full_topology: bool = True, channels: str = "all"):
        """
        :param: full_topology: bool indicating whether to retrieve the full topology.
        :param: channels: indicating "all" channels ("incoming" and "outgoing").
        :returns: unique_peerId_address: dict containing all unique
                source_peerId-source_address links
        """
        response = await self.api.get_channel_topology(full_topology=full_topology)

        unique_peerId_address = {}
        all_items = response[channels]

        for item in all_items:
            try:
                source_peer_id = item['sourcePeerId']
                source_address = item['sourceAddress']
            except KeyError as e:
                raise KeyError(f"Missing key in item dictionary: {str(e)}")

            if source_peer_id not in unique_peerId_address:
                unique_peerId_address[source_peer_id] = source_address

        return unique_peerId_address

    def mock_data_metrics_db(self):
        """
        Generates a mock metrics dictionary that mimics the metrics database output.
        :returns: a dictionary containing mock metrics data with peer IDs and network
        watcher IDs odered by a statistical measure computed on latency
        """
        metrics_dict = {
            "peer_id_1": {
                "netw": ["nw_1", "nw_3"]
            },
            "peer_id_2": {
                "netw": ["nw_1", "nw_2", "nw_4"]
            },
            "peer_id_3": {
                "netw": ["nw_2", "nw_3", "nw_4"]
            },
            "peer_id_4": {
                "netw": ["nw_1", "nw_2", "nw_3"]
            },
            "peer_id_5": {
                "netw": ["nw_1", "nw_2", "nw_3", "nw_4"]
            }
        }
        return metrics_dict

    def mock_data_subgraph(self):
        """
        Generates a dictionary that mocks the metrics received form the subgraph.
        :returns: a dictionary containing the data with safe stake addresses as key
                  and stake as value.
        """
        subgraph_dict = {
            "safe_1": {
                "stake": 10
            },
            "safe_2": {
                "stake": 55
            },
            "safe_3": {
                "stake": 23
            },
            "safe_4": {
                "stake": 85
            },
            "safe_5": {
                "stake": 62
            }
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
            with open(parameters_file_path, 'r') as file:
                contents = await asyncio.to_thread(json.load, file)
        except FileNotFoundError as e:
            log.error(f"The file '{file_name}' does not exist. {e}")
            log.error(traceback.format_exc())

        parameters = contents.get("parameters", {})
        equations = contents.get("equations", {})
        budget = contents.get("budget", {})

        try:
            jsonschema.validate(instance={"parameters": parameters, "equations": equations,
                                          "budget": budget}, schema=schema)
        except jsonschema.ValidationError as e:
            log.error(f"The file '{file_name}' does not follow the expected structure. {e}")
            log.error(traceback.format_exc())

        return parameters, equations, budget

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
                            rpch_node_peerID = [item['id'] for item in data if 'id' in item]
                            return rpch_node_peerID
                    else:
                        log.error(f"Received error code: {response.status}")
        except aiohttp.ClientError as e:
            log.error(f"An error occurred while making the request: {e}")
        except ValueError as e:
            log.error(f"An error occurred while parsing the response as JSON: {e}")
        except Exception as e:
            log.error(f"An unexpected error occurred: {e}")
        log.error(traceback.format_exc())

    def merge_topology_metricdb_subgraph(self, unique_peerId_address: dict,
                                        new_metrics_dict: dict,
                                        new_subgraph_dict: dict):
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
                        'safe_address': safe_address,
                        'netwatchers': new_metrics_dict[peer_id]['netw'],
                        'stake': new_subgraph_dict[safe_address]['stake']
                }
        except Exception as e:
            log.error(f"Error occurred while merging: {e}")
            log.error(traceback.format_exc())

        return merged_result

    def compute_ct_prob(self, parameters, equations, merged_result):
        """
        Evaluate the function for each stake value in the merged_result dictionary.
        :param: parameters: A dict containing the parameter values.
        :param: equations: A dict containing the equations and conditions.
        :param: A dict containing the data.
        :returns: A dict containing the probability distribution.
        """
        results = {}
        f_x_condition = equations['f_x']['condition']

        # compute transformed stake
        for key, value in merged_result.items():
            stake = value['stake']
            params = {param: value['value'] for param, value in parameters.items()}
            params['x'] = stake

            try:
                if eval(f_x_condition, params):
                    function = 'f_x'
                else:
                    function = 'g_x'

                formula = equations[function]['formula']
                result = eval(formula, params)
                results[key] = {'trans_stake': result}

            except Exception as e:
                log.error(f"Error evaluating function for peer ID {key}: {e}")
                log.error(traceback.format_exc())

        # compute ct probability
        sum_values = sum(result['trans_stake'] for result in results.values())
        for key in results:
            results[key]['prob'] = results[key]['trans_stake'] / sum_values

        # update dictionary with model results
        for key in merged_result:
            if key in results:
                merged_result[key].update(results[key])

        return merged_result

    def compute_expected_reward_savecsv(self, dataset: dict, budget: dict):
        """
        Computes the expected reward for each entry in the dataset based on the provided
        budget, saves the results to a CSV file, and returns the updated dataset.
        :param: dataset (dict): A dictionary containing the dataset entries.
        :param: budget (dict): A dictionary containing the budget information.
        :returns: dict: The updated dataset with the 'expected_reward' values
                        computed and added to each entry.
        """
        timestamp = time.strftime("%Y%m%d%H%M")
        folder_name = "expected_rewards"
        folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), folder_name)
        filename = f"expected_reward_{timestamp}.csv"
        file_path = os.path.join(folder_path, filename)

        try:
            os.makedirs(folder_path, exist_ok=True)
        except OSError as e:
            log.error(f"Error occurred while creating the folder: {e}")

        try:
            for entry in dataset.values():
                entry['expected_reward'] = entry['prob'] * budget['value']
        except KeyError as e:
            log.error(f"Error occurred while computing the expected reward: {e}")

        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['peer_id'] + list(dataset[next(iter(dataset))].keys()))
                for key, value in dataset.items():
                    writer.writerow([key] + list(value.values()))
        except OSError as e:
            log.error(f"Error occurred while writing to the CSV file: {e}")

        log.error(traceback.format_exc())

        return dataset



