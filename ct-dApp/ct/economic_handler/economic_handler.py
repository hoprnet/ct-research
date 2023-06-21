import logging
import json
import networkx as nx

from ct.hopr_api_helper import HoprdAPIHelper

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

    async def channel_topology(self, full_topology: bool = True):
        """
        Retrieves the channel topology of the monte rosa 1.0 network
        """
        response = await self.api.get_channel_topology(full_topology=full_topology)
        return response

    def create_channel_graph(response: dict, channels: str = "all"):
        """
        :param response: the response containing the channel topology data as a dict.
        :param channels: the channels to include in the graph. default is "all".
        :returns: the payment channel graph based on the provided response.
        """
        try:
            response_data = json.loads(response)
            logging.info("Successfully loaded response data")
        except json.JSONDecodeError as e:
            logging.error("Failed to load response data. Error: {}".format(e))
            raise

        # Create a directed network graph
        graph = nx.DiGraph()

        try:
            for data in response_data[channels]:
                # node
                source_peer_id = data["sourcePeerId"]
                destination_peer_id = data["destinationPeerId"]

                # edge attributes
                destination_address = data["destinationAddress"]
                channel_id = data["channelId"]
                balance = float(data["balance"]) / 1e18
                status = data["status"]
                commitment = data["commitment"]
                ticket_epoch = int(data["ticketEpoch"])
                ticket_index = int(data["ticketIndex"])
                channel_epoch = int(data["channelEpoch"])
                closure_time = data["closureTime"]

                graph.add_edge(
                    source_peer_id,
                    destination_peer_id,
                    destination_address = destination_address,
                    channel_id=channel_id,
                    balance=balance,
                    status=status,
                    commitment=commitment,
                    ticket_epoch=ticket_epoch,
                    ticket_index=ticket_index,
                    channel_epoch=channel_epoch,
                    closure_time=closure_time,
                )

                # node attributes
                graph.nodes[source_peer_id]["source_address"] = data["sourceAddress"]

            logging.info("Channel graph successfully generated")
        except KeyError as e:
            logging.error("Failed to generate channel graph. Missing key: {}".format(e))
            raise

        return graph