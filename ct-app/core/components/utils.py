import json
import os
import random
import string
from os import environ
from typing import Any

import aiohttp
from aiohttp import ClientSession
from google.cloud import storage

from core.model import EconomicModel, Peer, SubgraphEntry, TopologyEntry


class Utils:
    @classmethod
    def randomString(cls, length: int, alpha: bool = True, numeric: bool = True):
        choices = ""
        if alpha:
            choices += string.ascii_letters
        if numeric:
            choices += string.digits

        return "".join(random.choices(choices, k=length))

    @classmethod
    def envvar(cls, var_name: str, default: Any = None, type: type = str):
        if var_name in environ:
            return type(environ[var_name])
        else:
            return default

    @classmethod
    def envvarWithPrefix(cls, prefix: str, type=str) -> dict[str, Any]:
        var_dict = {
            key: type(v) for key, v in environ.items() if key.startswith(prefix)
        }

        return dict(sorted(var_dict.items()))

    @classmethod
    def nodesAddresses(cls, address_prefix: str, keyenv: str) -> tuple[list[str], str]:
        addresses = Utils.envvarWithPrefix(address_prefix).values()
        key = Utils.envvar(keyenv)

        return addresses, key

    @classmethod
    async def httpPOST(cls, url, data):
        async def post(session: ClientSession, url: str, data: dict):
            async with session.post(url, json=data) as response:
                status = response.status
                response = await response.json()
                return status, response

        async with aiohttp.ClientSession() as session:
            try:
                status, response = await post(session, url, data)
            except Exception:
                return None, None
            else:
                return status, response

    @classmethod
    def mergeTopologyPeersSubgraph(
        cls,
        topology_list: list[TopologyEntry],
        peers_list: list[Peer],
        subgraph_list: list[SubgraphEntry],
    ):
        """
        Merge metrics and subgraph data with the unique peer IDs, addresses,
        balance links.
        :param: topology_dict: A dict mapping peer IDs to node addresses.
        :param: peers_list: A dict containing metrics with peer ID as the key.
        :param: subgraph_dict: A dict containing subgraph data with safe address as the key.
        :returns: A dict with peer ID as the key and the merged information.
        """
        merged_result: list[Peer] = []

        network_addresses = [p.address for p in peers_list]

        # Merge based on peer ID with the channel topology as the baseline
        for topology_entry in topology_list:
            peer = topology_entry.to_peer()

            entries = [e for e in subgraph_list if e.has_address(peer.address.address)]
            if len(entries) > 0:
                subgraph_entry: SubgraphEntry = entries[0]
            else:
                subgraph_entry = SubgraphEntry(None, None, None)

            peer.safe_address = subgraph_entry.safe_address
            peer.safe_balance = subgraph_entry.wxHoprBalance

            if peer.complete and peer.address in network_addresses:
                merged_result.append(peer)

        return merged_result

    @classmethod
    def allowManyNodePerSafe(cls, peers: list[Peer]):
        """
        Split the stake managed by a safe address equaly between the nodes
        that the safe manages.
        :param: peer: list of peers
        :returns: nothing.
        """
        safe_counts = {peer.safe_address: 0 for peer in peers}

        # Calculate the number of safe_addresses related to a node address
        for peer in peers:
            safe_counts[peer.safe_address] += 1

        # Update the input_dict with the calculated splitted_stake
        for peer in peers:
            peer.safe_address_count = safe_counts[peer.safe_address]

    @classmethod
    def excludeElements(cls, source_data: list[Peer], blacklist: list) -> list[Peer]:
        """
        Removes elements from a dictionary based on a blacklist.
        :param: source_data (dict): The dictionary to be updated.
        :param: blacklist (list): A list containing the keys to be removed.
        :returns: nothing.
        """

        peer_addresses = [peer.address for peer in source_data]
        indexes = [
            peer_addresses.index(address)
            for address in blacklist
            if address in peer_addresses
        ]

        # Remove elements from the list
        excluded = []
        for index in sorted(indexes, reverse=True):
            peer: Peer = source_data.pop(index)
            excluded.append(peer)

        return excluded

    @classmethod
    def rewardProbability(cls, peers: list[Peer]) -> list[int]:
        """
        Evaluate the function for each stake value in the eligible_peers dictionary.
        :param eligible_peers: A dict containing the data.
        :returns: nothing.
        """

        indexes_to_remove = [
            idx for idx, peer in enumerate(peers) if peer.has_low_stake
        ]

        # remove entries from the list
        for index in sorted(indexes_to_remove, reverse=True):
            peers.pop(index)

        # compute ct probability
        total_tf_stake = sum(peer.transformed_stake for peer in peers)
        for peer in peers:
            peer.reward_probability = peer.transformed_stake / total_tf_stake

        return indexes_to_remove

    @classmethod
    def EconomicModelFromGCPFile(cls, filename: str):
        """
        Reads parameters and equations from a JSON file and validates it using a schema.
        :param: filename (str): The name of the JSON file containing the parameters
        and equations.
        :returns: EconomicModel: Instance containing the model parameters,equations,
        budget parameters.
        """
        parameters_file_path = os.path.join("assets", filename)

        contents = Utils.jsonFromGCP("ct-platform-ct", parameters_file_path, None)

        model = EconomicModel.fromDict(contents)

        return model

    @classmethod
    def jsonFromGCP(cls, bucket_name, blob_name, schema=None):
        """
        Reads a JSON file and validates its contents using a schema.
        :param: bucket_name: The name of the bucket
        :param: blob_name: The name of the blob
        ;param: schema (opt): The validation schema
        :returns: (dict): The contents of the JSON file.
        """

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        with blob.open("r") as f:
            contents = json.load(f)

        # if schema is not None:
        #     try:
        #         jsonschema.validate(
        #             contents,
        #             schema=schema,
        #         )
        #     except jsonschema.ValidationError as e:
        #         log.exception(
        #             f"The file in'{blob_name}' does not follow the expected structure. {e}"
        #         )
        #         return {}

        return contents
