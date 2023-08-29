import asyncio
from copy import deepcopy
import random
import time


from tools.decorator import connectguard, formalin
from tools.hopr_node import HOPRNode
from tools.utils import getlogger, post_dictionary

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
        self.peers = list[str]()

        # a dict to keep the max_lat_count latency measures along with the timestamp
        self.latency = dict[str, dict]()
        self.last_peer_transmission: float = 0

        self.max_lat_count = max_lat_count
        self._mock_mode = False

        self.latency_lock = asyncio.Lock()

        ############### MOCKING ###################
        # set of 100 random peers
        self.mocking_peers = list(
            [
                "0x" + "".join(random.choices("0123456789abcdef", k=20))
                for _ in range(20)
            ]
        )
        ###########################################

        super().__init__(url, key)

    @property
    def mock_mode(self):
        return self._mock_mode

    @mock_mode.setter
    def mock_mode(self, value: bool):
        self._mock_mode = value

        if self._mock_mode:
            index = random.randint(0, 100)
            self.peer_id = f"<mock-node-address-{index:03d}>"

    @formalin(message="Gathering peers", sleep=20)
    @connectguard
    async def gather_peers(self, quality: float = 0.2):
        """
        Long-running task that continously updates the set of peers connected to this
        node.
        :param quality: the minimum quality of the peers to be detected
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        if self.mock_mode:
            number_to_pick = random.randint(5, 10)
            found_peers = random.sample(self.mocking_peers, number_to_pick)
        else:
            found_peers = await self.api.peers(param="peerId", quality=quality)

        self.peers = found_peers
        log.info(f"Found {len(found_peers)} peers {', '.join(found_peers)}")

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

        if self.mock_mode:
            latency = random.randint(10, 100) if random.random() < 0.8 else 0
        else:
            latency = await self.api.ping(rand_peer, "latency")

        # latency update rule is:
        # - if latency measure fails:
        #     - if the peer is not known, add it with value -1 and set timestamp
        #     - if the peer is known and the last measure is recent, do nothing
        # - if latency measure succeeds, always update
        now = time.time()
        async with self.latency_lock:
            if latency != 0:
                log.debug(f"Measured latency to {rand_peer}: {latency}ms")

                self.latency[rand_peer] = {"value": latency, "timestamp": now}
                return

            log.warning(f"Failed to ping {rand_peer}")

            if (
                rand_peer not in self.latency
                or self.latency[rand_peer]["value"] is None
            ):
                log.debug(f"Adding {rand_peer} to latency dictionary with value -1")

                self.latency[rand_peer] = {"value": -1, "timestamp": now}
                return

            log.debug(f"Keeping {rand_peer} in latency dictionary (recent measure)")

    @formalin(message="Initiated peers transmission", sleep=5)
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
                f"Transmission skipped. {len(selected_peers_values)} peers waiting.."
            )
            return

        data = {
            "id": self.peer_id,
            "peers": {peer: value for peer, value in selected_peers_values},
        }

        # send peer list to aggregator.
        try:
            success = await post_dictionary(self.posturl, data)
        except Exception:
            log.error("Error transmitting peer dictionary")
            return

        if not success:
            log.error("Peers transmission failed")
            return

        filtered_peers = [peer for peer, _ in selected_peers_values]

        log.info(
            f"Transmitted {len(filtered_peers)} peers: {', '.join(filtered_peers)}"
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
        if self.mock_mode:
            native_balance = random.randint(100, 1000)
            hopr_balance = random.randint(100, 1000)

            balances = {"native": native_balance, "hopr": hopr_balance}
        else:
            balance = await self.api.balance("native")
            balances = {"native": balance}

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

        log.info(f"Transmitted balances: {data['balances']}")

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info(f"Starting instance connected to '{self.peer_id}'")
        if self.tasks:
            return

        self.started = True
        if not self.mock_mode:
            self.tasks.add(asyncio.create_task(self.connect(address="hopr")))

        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))
        # self.tasks.add(asyncio.create_task(self.transmit_balance()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this instance
        """
        log.debug(f"Stopping instance {self.peer_id}")

        self.started = False
        for task in self.tasks:
            task.add_done_callback(self.tasks.discard)
            task.cancel()

        self.tasks = set()
