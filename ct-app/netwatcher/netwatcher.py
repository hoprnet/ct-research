import asyncio
import random
import time

from aiohttp import ClientSession

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

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dict to keep the max_lat_count latency measures {peer: [51, 23, ...]}
        self.latency = dict[str, int]()
        self.last_peer_transmission: float = 0

        self.max_lat_count = max_lat_count
        self._mock_mode = False

        ############### MOCKING ###################
        # set of 100 random peers
        self.mocking_peers = set(
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

    @formalin(message="Gathering peers", sleep=60 * 0.5)
    @connectguard
    async def gather_peers(self, quality: float = 1.0):
        """
        Long-running task that continously updates the set of peers connected to this
        node.
        :param quality:
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        if self.mock_mode:
            number_to_pick = random.randint(5, 10)
            found_peers = random.sample(self.mocking_peers, number_to_pick)
        else:
            found_peers = await self.api.peers(param="peerId", quality=quality)

        new_peers = set(found_peers) - set(self.peers)

        [self.peers.add(peer) for peer in new_peers]
        log.info(f"Found new peers {', '.join(new_peers)} (total of {len(self.peers)})")

    @formalin(message="Pinging peers", sleep=0.1)
    @connectguard
    async def ping_peers(self):
        """
        Pings the peers of this node and records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a list of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.
        """

        # pick a random peer to ping among all peers
        rand_peer = random.choice(self.peers)

        if self.mock_mode:
            latency = random.randint(10, 100) if random.random() < 0.8 else 0
        else:
            latency = await self.api.ping(rand_peer, "latency")

        if latency is not None:
            self.latency[rand_peer] = latency

    @formalin(message="Initiated peers transmission", sleep=5)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        peers_to_send: dict[str, int] = {}
        trigger_transmission = False

        for (peer, latency), _ in zip(self.latency.items(), range(self.max_lat_count)):
            peers_to_send[peer] = latency

        if len(peers_to_send) == self.max_lat_count:
            trigger_transmission = True
            log.info("Peers transmission triggered by latency dictionary size")

        elif time.time() - self.last_peer_transmission > 60 * 5:  # 5 minutes
            trigger_transmission = True
            log.info("Peers transmission triggered by timestamp")

        if not trigger_transmission:
            return

        data = {"id": self.peer_id, "list": peers_to_send}

        async with ClientSession() as session:
            success = await post_dictionary(session, self.posturl, data)

            if not success:
                await asyncio.sleep(5)
                success = await post_dictionary(session, self.posturl, data)

        if not success:
            return

        log.info(
            f"Transmitted {len(list(peers_to_send))} peers: {', '.join(peers_to_send)}"
        )

        # completely remove the transmitted key-value pair from self.latency
        for peer in peers_to_send:
            self.latency.pop(peer, None)
        self.last_peer_transmission = time.time()

    @formalin(message="Sending node balance", sleep=60 * 5)
    @connectguard
    async def transmit_balance(self):
        if self.mock_mode:
            balance = random.randint(100, 1000)
        else:
            balance = await self.api.balance("native")

        log.info(f"Got native balance: {balance}")

        data = {"id": self.peer_id, "balances": {"native": balance}}

        async with ClientSession() as session:
            success = await post_dictionary(session, self.balanceurl, data)

            if not success:
                await asyncio.sleep(5)
                await post_dictionary(session, self.balanceurl, data)

        if not success:
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
        else:
            self.peer_id = "<mock_peer_id>"

        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_balance()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this instance
        """
        log.debug(f"Stopping instance {self.peer_id}")

        self.started = False
        for task in self.tasks:
            task.cancel()
        self.tasks = set()
