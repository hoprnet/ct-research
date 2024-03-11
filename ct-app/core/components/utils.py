import csv
import json
import os
import time
from datetime import datetime, timedelta
from os import environ
from typing import Any

import aiohttp
from aiohttp import ClientSession
from celery import Celery
from google.cloud import storage
from scripts.list_required_parameters import list_parameters

from core.model.address import Address
from core.model.peer import Peer
from core.model.subgraph_entry import SubgraphEntry
from core.model.topology_entry import TopologyEntry

from .baseclass import Base


class Utils(Base):
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
    def envvarExists(cls, var_name: str) -> bool:
        return var_name in environ

    @classmethod
    def checkRequiredEnvVar(cls, folder: str):
        all_set_flag = True
        for param in list_parameters(folder):
            exists = Utils.envvarExists(param)
            cls().info(f"{'✅' if exists else '❌'} {param}")
            all_set_flag *= exists

        return all_set_flag

    @classmethod
    def nodesAddresses(
        cls, address_prefix: str, keyenv: str
    ) -> tuple[list[str], list[str]]:
        addresses = Utils.envvarWithPrefix(address_prefix).values()
        keys = Utils.envvarWithPrefix(keyenv).values()

        return list(addresses), list(keys)

    @classmethod
    async def httpPOST(
        cls, url: str, data: dict, timeout: int = 60
    ) -> tuple[int, dict]:
        async def post(session: ClientSession, url: str, data: dict, timeout: int):
            async with session.post(url, json=data, timeout=timeout) as response:
                status = response.status
                response = await response.json()
                return status, response

        async with aiohttp.ClientSession() as session:
            try:
                status, response = await post(session, url, data, timeout)
            except Exception:
                return None, None
            else:
                return status, response

    @classmethod
    def mergeTopoPeersSafes(
        cls,
        topology: list[TopologyEntry],
        peers: list[Peer],
        safes: list[SubgraphEntry],
    ):
        merged_result: list[Peer] = []
        addresses = [item.node_address for item in topology]

        for address in addresses:
            peer = next(filter(lambda p: p.address.address == address, peers), None)
            topo = next(filter(lambda t: t.node_address == address, topology), None)
            safe = next(filter(lambda s: s.node_address == address, safes), None)

            if peer is None or topo is None or safe is None:
                continue

            peer.safe_address = safe.safe_address
            peer.safe_balance = safe.wxHoprBalance
            peer.safe_allowance = float(safe.safe_allowance)
            peer.channel_balance = topo.channels_balance

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
    def exclude(cls, source_data: list[Peer], blacklist: list[Address]) -> list[Peer]:
        """
        Removes elements from a dictionary based on a blacklist.
        :param: source_data (dict): The dictionary to be updated.
        :param: blacklist (list): A list containing the keys to be removed.
        :returns: nothing.
        """

        addresses = [peer.address for peer in source_data]
        indexes = [addresses.index(item) for item in blacklist if item in addresses]

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
        """

        results: dict[str, dict] = {}
        for c in channels:
            if not (
                hasattr(c, "source_peer_id")
                and hasattr(c, "source_address")
                and hasattr(c, "status")
            ):
                continue

            if c.status != "Open":
                continue

            if c.source_peer_id not in results:
                results[c.source_peer_id] = {
                    "source_node_address": c.source_address,
                    "channels_balance": 0,
                }

            results[c.source_peer_id]["channels_balance"] += int(c.balance) / 1e18

        return results

    @classmethod
    def taskSendMessage(
        cls,
        app: Celery,
        relayer_id: str,
        expected: int,
        ticket_price: float,
        timestamp: float = None,
        attempts: int = 0,
        task_name: str = "send_1_hop_message",
    ):
        app.send_task(
            task_name,
            args=(relayer_id, expected, ticket_price, timestamp, attempts),
            queue="send_messages",
        )
