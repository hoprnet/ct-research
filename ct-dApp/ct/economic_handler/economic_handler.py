import logging
import os
import traceback
import json
import jsonschema

from ct.hopr_api_helper import HoprdAPIHelper
from .parameters_schema import schema

# Configure logging to output log messages to the console
logging.basicConfig(level=logging.DEBUG)
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

    def read_parameters_and_equations(self, file_name: str = "parameters.json"):
        """
        Reads parameters and equations from a JSON file and validates it using a schema.
        :param: file_name (str): The name of the JSON file containing the parameters
        and equations. Defaults to "parameters.json".
        :returns: tuple: The first dictionary contains the parameters and the second
        dictionary contains the equations.
        """
        script_directory = os.path.dirname(os.path.abspath(__file__))
        parameters_file_path = os.path.join(script_directory, file_name)

        try:
            with open(parameters_file_path, 'r') as file:
                contents = json.load(file)
        except FileNotFoundError as e:
            log.error(f"The file '{file_name}' does not exist. {e}")
            log.error(traceback.format_exc())

        parameters = contents.get("parameters", {})
        equations = contents.get("equations", {})

        try:
            jsonschema.validate(instance={"parameters": parameters, "equations": equations}, schema=schema)
        except jsonschema.ValidationError as e:
            log.error(f"The file '{file_name}' does not follow the expected structure. {e}")
            log.error(traceback.format_exc())

        return parameters, equations