import csv
import json
import os
import random
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from aiohttp import ClientSession
from google.cloud import storage

from core.model.address import Address
from core.model.peer import Peer
from core.model.subgraph_entry import SubgraphEntry
from core.model.topology_entry import TopologyEntry

from .baseclass import Base
from .channelstatus import ChannelStatus
from .environment_utils import EnvironmentUtils


class Utils(Base):
    @classmethod
    def nodesAddresses(
        cls, address_prefix: str, keyenv: str
    ) -> tuple[list[str], list[str]]:
        """
        Returns a tuple containing the addresses and keys of the nodes.
        :param address_prefix: The prefix of the environment variables containing addresses.
        :param keyenv: The prefix of the environment variables containing keys.
        :returns: A tuple containing the addresses and keys.
        """
        addresses = EnvironmentUtils.envvarWithPrefix(address_prefix).values()
        keys = EnvironmentUtils.envvarWithPrefix(keyenv).values()

        return list(addresses), list(keys)

    @classmethod
    async def httpPOST(cls, url: str, data: dict) -> tuple[int, dict]:
        """
        Performs an HTTP POST request.
        :param url: The URL to send the request to.
        :param data: The data to be sent.
        :returns: A tuple containing the status code and the response.
        """

        async def _post(session: ClientSession, url: str, data: dict):
            async with session.post(url, json=data) as response:
                status = response.status
                response = await response.json()
                return status, response

        async with aiohttp.ClientSession() as session:
            try:
                status, response = await _post(session, url, data)
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
        :param topology_dict: A dict mapping peer IDs to node addresses.
        :param peers_list: A dict containing metrics with peer ID as the key.
        :param subgraph_dict: A dict containing subgraph data with safe address as key.
        :returns: A dict with peer ID as the key and the merged information.
        """
        merged_result: list[Peer] = []
        network_addresses = [p.address for p in peers_list]
        peer_versions = {p.address: p.version for p in peers_list}

        # Merge based on peer ID with the channel topology as the baseline
        for topology_entry in topology_list:
            peer = topology_entry.to_peer()

            entries = [e for e in subgraph_list if e.has_address(peer.address.address)]
            if len(entries) > 0:
                subgraph_entry: SubgraphEntry = entries[0]
            else:
                subgraph_entry = SubgraphEntry(None, None, None, None)

            peer.safe_address = subgraph_entry.safe_address
            peer.safe_balance = subgraph_entry.wxHoprBalance

            if subgraph_entry.safe_allowance is not None:
                peer.safe_allowance = float(subgraph_entry.safe_allowance)
            else:
                peer.safe_allowance = None

            if peer.complete and peer.address in network_addresses:
                peer.version = peer_versions[peer.address]
                merged_result.append(peer)

        return merged_result

    @classmethod
    def allowManyNodePerSafe(cls, peers: list[Peer]):
        """
        Split the stake managed by a safe address equaly between the nodes
        that the safe manages.
        :param peer: list of peers
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
    def excludeElements(
        cls, source_data: list[Peer], blacklist: list[Address]
    ) -> list[Peer]:
        """
        Removes elements from a dictionary based on a blacklist.
        :param source_data (dict): The dictionary to be updated.
        :param blacklist (list): A list containing the keys to be removed.
        :returns: A list containing the removed elements.
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
        :param peers: A dict containing the data.
        :returns: A list containing the excluded elements due to low stake.
        """

        indexes_to_remove = [
            idx for idx, peer in enumerate(peers) if peer.has_low_stake
        ]

        # remove entries from the list
        excluded: list[Peer] = []
        for index in sorted(indexes_to_remove, reverse=True):
            peer: Peer = peers.pop(index)
            excluded.append(peer)

        # compute ct probability
        total_tf_stake = sum(peer.transformed_stake for peer in peers)
        for peer in peers:
            peer.reward_probability = peer.transformed_stake / total_tf_stake

        return excluded

    @classmethod
    def jsonFromGCP(cls, bucket_name: str, blob_name: str):
        """
        Reads a JSON file and validates its contents using a schema.
        :param bucket_name: The name of the bucket
        :param blob_name: The name of the blob
        :returns: The contents of the JSON file.
        """

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        with blob.open("r") as f:
            contents = json.load(f)

        return contents

    @classmethod
    def stringArrayToGCP(cls, bucket_name: str, blob_name: str, data: list[str]):
        """
        Write a blob from GCS using file-like IO
        :param bucket_name: The name of the bucket
        :param blob_name: The name of the blob
        :param data: The data to write
        """
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        with blob.open("w") as f:
            writer = csv.writer(f)
            writer.writerows(data)

    @classmethod
    def generateFilename(cls, prefix: str, foldername: str, extension: str = "csv"):
        """
        Generates a filename with the following format:
        <prefix>_<timestamp>.<extension>
        :param prefix: The prefix of the filename
        :param foldername: The folder where the file will be stored
        :param extension: The extension of the file
        :returns: The filename
        """
        timestamp = time.strftime("%Y%m%d%H%M%S")

        if extension.startswith("."):
            extension = extension[1:]

        filename = f"{prefix}_{timestamp}.{extension}"
        return os.path.join(foldername, filename)

    @classmethod
    def nextEpoch(cls, seconds: int) -> datetime:
        """
        Calculates the delay until the next whole `minutes`min and `seconds`sec.
        :param seconds: next whole second to trigger the function
        :returns: The next epoch
        """
        if seconds == 0:
            raise ValueError("'seconds' must be greater than 0")

        dt, min_date, delta = datetime.now(), datetime.min, timedelta(seconds=seconds)
        next_timestamp = min_date + round((dt - min_date) / delta + 0.5) * delta

        return next_timestamp

    @classmethod
    def nextDelayInSeconds(cls, seconds: int) -> int:
        """
        Calculates the delay until the next whole `minutes`min and `seconds`sec.
        :param seconds: next whole second to trigger the function
        :returns: The delay in seconds.
        """
        if seconds == 0:
            return 1

        delay = Utils.nextEpoch(seconds) - datetime.now()

        if delay.total_seconds() < 1:
            return seconds
        else:
            return int(delay.total_seconds())

    @classmethod
    async def aggregatePeerBalanceInChannels(cls, channels: list) -> dict[str, dict]:
        """
        Returns a dict containing all unique source_peerId-source_address links.
        :param channels: The list of channels.
        :returns: A dict containing all peerIds-balanceInChannels links.
        """

        results: dict[str, dict] = {}
        for c in channels:
            if not (
                hasattr(c, "source_peer_id")
                and hasattr(c, "source_address")
                and hasattr(c, "status")
                and hasattr(c, "balance")
            ):
                continue

            if ChannelStatus(c.status) != ChannelStatus.Open:
                continue

            if c.source_peer_id not in results:
                results[c.source_peer_id] = {
                    "source_node_address": c.source_address,
                    "channels_balance": 0,
                }

            results[c.source_peer_id]["channels_balance"] += int(c.balance) / 1e18

        return results

    @classmethod
    def splitDict(cls, src: dict[str, Any], bins: int) -> list[dict[str, Any]]:
        """
        Splits randomly a dict into multiple sub-dictionary of almost equal sizes.
        :param src: The dict to be split.
        :param bins: The number of sub-dictionaries.
        :returns: A list containing the sub-dictionaries.
        """
        # Split the dictionary into multiple sub-dictionaries
        split = [{} for _ in range(bins)]

        # Assign a random number to each element in the dictionary
        for idx, (key, value) in enumerate(random.sample(src.items(), len(src))):
            split[idx % bins][key] = value

        return split
