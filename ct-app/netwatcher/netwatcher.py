import asyncio
from copy import deepcopy
import random
import time

from tools.decorator import connectguard, formalin
from tools.hopr_node import HOPRNode
from tools.utils import getlogger, post_dictionary, envvar

log = getlogger()


class NetWatcher(HOPRNode):
    """
    NetWatcher implementation. This class is used to detect peers and send them to the
    Aggregator via a POST request.
    """

    def __init__(
        self, url: str, key: str, posturl: str, balanceurl: str, max_lat_count: int = 10
    ):
        """
        Initialisation of the class.
        :param url: the url of the hopr node
        :param key: the key of the hopr node
        :param posturl: the url of the Aggregator to send the peers to
        """
        # assign unique uuid as a string
        self.posturl = posturl
        self.balanceurl = balanceurl

        # a list to keep the peers of this node
        self.peers = list[dict]()

        # a dict to keep the max_lat_count latency measures along with the timestamp
        self.latency = dict[str, dict]()
        self.last_peer_transmission: float = 0

        # a dict to store all the peers that have been pinged at least once.
        # Used to open channels
        self.peers_pinged_once = {}

        self.max_lat_count = max_lat_count

        self.latency_lock = asyncio.Lock()
        self.peers_pinged_once_lock = asyncio.Lock()

        super().__init__(url, key)

    @formalin(message="Gathering peers", sleep=60)
    @connectguard
    async def gather_peers(self, quality: float = 0.5):
        """
        Long-running task that continously updates the set of peers connected to this
        node.
        :param quality: the minimum quality of the peers to be detected
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        found_peers = await self.api.peers(
            params=["peer_id", "peer_address"], quality=quality
        )

        _short_peers = [".." + peer["peer_id"][-5:] for peer in found_peers]
        self.peers = found_peers
        log.info(f"Found {len(found_peers)} peers {', '.join(_short_peers)}")

    @formalin(message="Pinging peers", sleep=1)
    @connectguard
    async def ping_peers(self):
        """
        Pings the peers of this node and records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a list of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.
        """

        # if no peer is available, simply wait for 10 seconds and hope that new peers
        # are found in the meantime
        if len(self.peers) == 0:
            await asyncio.sleep(10)
            return

        # pick a random peer to ping among all peers
        rand_peer = random.choice(self.peers)
        rand_peer_id = rand_peer["peer_id"]
        rand_peer_address = rand_peer["peer_address"]  # noqa: F841

        if envvar("MOCK_LATENCY", int):
            latency = random.randint(0, 100)
        else:
            latency = await self.api.ping(rand_peer_id, "latency")
            log.debug(f"Measured latency to {rand_peer_id[-5:]}: {latency}ms")

        # latency update rule is:
        # - if latency measure fails:
        #     - if the peer is not known, add it with value -1 and set timestamp
        #     - if the peer is known and the last measure is recent, do nothing
        # - if latency measure succeeds, always update
        if latency != 0:
            async with self.peers_pinged_once_lock:
                self.peers_pinged_once[rand_peer_id] = rand_peer_address

        now = time.time()
        async with self.latency_lock:
            if latency != 0:
                self.latency[rand_peer_id] = {"value": latency, "timestamp": now}

                return

            log.warning(f"Failed to ping {rand_peer_id}")

            if (
                rand_peer_id not in self.latency
                or self.latency[rand_peer_id]["value"] is None
            ):
                log.debug(f"Adding {rand_peer_id} to latency dictionary with value -1")

                self.latency[rand_peer_id] = {"value": -1, "timestamp": now}
                return

            log.debug(f"Keeping {rand_peer_id} in latency dictionary (recent measure)")

    @formalin(message="Initiated peers transmission", sleep=20)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        peers_to_send: dict[str, int] = {}

        # access the peers address in the latency dictionary in a thread-safe way
        async with self.latency_lock:
            peers_measures = deepcopy(self.latency)

        # convert the latency dictionary to a simpler dictionary for the aggregator
        now = time.time()
        for peer, measure in peers_measures.items():
            if (
                now - measure["timestamp"] > 60 * 60 * 2
                and measure["value"] is not None
            ):
                measure["value"] = -1

            if measure["value"] is None:
                continue
            if measure["value"] == 0:
                continue

            peers_to_send[peer] = measure["value"]

        # pick randomly `self.max_lat_count` peers from peer values
        selected_peers_values = random.sample(
            list(peers_to_send.items()), k=min(self.max_lat_count, len(peers_to_send))
        )

        # checks if transmission needs to be triggered by peer-list size
        if len(selected_peers_values) == self.max_lat_count:
            log.info("Peers transmission triggered by latency dictionary size")
        # checks if transmission needs to be triggered by timestamp
        elif (
            time.time() - self.last_peer_transmission > 60 * 5
            and len(selected_peers_values) != 0
        ):  # 5 minutes
            log.info("Peers transmission triggered by timestamp")
        else:
            log.info(
                f"Peer transmission skipped. {len(selected_peers_values)} peers waiting.."
            )
            return

        data = {
            "id": self.peer_id,
            "peers": {peer: value for peer, value in selected_peers_values},
        }

        # send peer list to aggregator.
        try:
            success = await post_dictionary(self.posturl, data)
        except Exception as e:
            log.error(f"Exception while transmitting peers: {e}")
            return

        if not success:
            log.error("Peers transmission failed")
            return

        filtered_peers = [peer for peer, _ in selected_peers_values]

        _short_filter_peers = [".." + peer[-5:] for peer in filtered_peers]
        log.info(
            f"Transmitted {len(filtered_peers)} peers: {', '.join(_short_filter_peers)}"
        )

        # reset the transmitted key-value pair from self.latency in a
        # thread-safe way
        async with self.latency_lock:
            self.last_peer_transmission = time.time()
            for peer in filtered_peers:
                self.latency[peer] = {"value": None, "timestamp": 0}

    @formalin(message="Sending node balance", sleep=60 * 5)
    @connectguard
    async def transmit_balance(self):
        balances = await self.api.balances()

        log.info(f"Got balances: {balances}")

        data = {"id": self.peer_id, "balances": balances}

        # sends balance to aggregator.
        try:
            success = await post_dictionary(self.balanceurl, data)
        except Exception:
            log.exception("Error transmitting balance dictionary")
            return

        if not success:
            log.error("Balance transmission failed")
            return

        log.info("Transmitted balances")

    @formalin(message="Closing incoming channels", sleep=30)
    @connectguard
    async def close_incoming_channels(self):
        """
        Closes all incoming channels.
        """
        incoming_channels_ids = await self.api.incoming_channels(only_id=True)

        if len(incoming_channels_ids) == 0:
            log.info("No incoming channels to close")
            return

        log.warning(f"Discovered {len(incoming_channels_ids)} incoming channels")

        for channel_id in incoming_channels_ids:
            log.warning(f"Closing channel {channel_id}")
            await self.api.close_channel(channel_id)

        log.info(f"Closed {len(incoming_channels_ids)} incoming channels")

    @formalin(message="Opening channels to peers", sleep=20)
    @connectguard
    async def open_channels(self):
        """
        Open channels to peers that have been successfully pinged at least once.
        """
        async with self.peers_pinged_once_lock:
            local_peers_pinged_once = deepcopy(self.peers_pinged_once)

        # getting all channels to filter the outgoing ones from us, and retrieve the
        # destination addresses of opened outgoing channels
        channels = await self.api.all_channels(False)

        outgoing_channels_peer_addresses = []
        for channel in channels.all:
            if channel.source_peer_id == self.peer_id and channel.status == "Open":
                outgoing_channels_peer_addresses.append(channel.destination_address)

        num_peers = len(local_peers_pinged_once)

        sample_indexes = random.sample(range(num_peers), min(num_peers, 5))
        subdict_local_peers_pinged_once = {
            list(local_peers_pinged_once.keys())[i]: list(
                local_peers_pinged_once.values()
            )[i]
            for i in sample_indexes
        }

        for peer_id, peer_address in subdict_local_peers_pinged_once.items():
            if peer_address in outgoing_channels_peer_addresses:
                log.info(
                    f"Channel to {peer_id}({peer_address}) already opened. Skipping.."
                )
                continue

            log.info(f"Opening channel to {peer_id}({peer_address})")
            success = await self.api.open_channel(
                peer_address, envvar("CHANNEL_INITIAL_BALANCE")
            )
            log.info(f"Channel to {peer_id}({peer_address}) opened: {success}")

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info("Starting instance")
        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.connect()))
        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_balance()))
        self.tasks.add(asyncio.create_task(self.open_channels()))
        # self.tasks.add(asyncio.create_task(self.close_incoming_channels()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this instance
        """
        log.debug("Stopping instance")

        self.started = False
        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()

        self.tasks = set()
