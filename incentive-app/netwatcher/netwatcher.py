import asyncio
import logging
import random
import uuid

from aiohttp import ClientSession

from tools.decorator import connectguard, formalin, wakeupcall
from tools.hopr_node import HOPRNode

log = logging.getLogger(__name__)


class NetWatcher(HOPRNode):
    """
    NetWatcher implementation. This class is used to detect peers and send them to the
    Aggregator via a POST request.
    """

    def __init__(self, url: str, key: str, posturl: str, max_lat_count: int = 10):
        """
        Initialisation of the class.
        :param url: the url of the hopr node
        :param key: the key of the hopr node
        :param posturl: the url of the Aggregator to send the peers to
        """
        # assign unique uuid as a string
        self.id = str(uuid.uuid4())
        self.posturl = posturl

        # a set to keep the peers of this node, see:
        self.peers = set[str]()

        # a dict to keep the max_lat_count latency measures {peer: [51, 23, ...]}
        self.latency = dict[str, list]()

        self.max_lat_count = max_lat_count

        ############### MOCKING ###################
        # set of 100 random peers
        self.all_peers = set(
            [
                "0x" + "".join(random.choices("0123456789abcdef", k=20))
                for _ in range(20)
            ]
        )
        ###########################################

        super().__init__(url, key)

    def wipe_peers(self):
        """
        Wipes the list of peers
        """
        log.info("Wiping peers")

        self.peers.clear()
        self.latency.clear()

    async def _post_list(self, session: ClientSession, peers: list, latencies: list):
        """
        Sends the detected peers to the Aggregator. For the moment, only the last
        latency is transmitted for each peer.
        :param session: the aiohttp session
        :param peers: the list of peers
        :param latencies: the list of latencies
        """

        # list of shorten peer ids (only for convenience. will be removed)
        short_list = [p[-5:] for p in peers]

        # list standard peer ids (creating a secure copy of the list)
        long_list = [p for p in peers]

        latency_dict = {}
        for i in range(len(short_list)):
            latency = latencies[long_list[i]][-1] if long_list[i] in latencies else None

            latency_dict[short_list[i]] = latency

        data = {"id": self.id, "list": latency_dict}

        try:
            async with session.post(self.posturl, json=data) as response:
                if response.status == 200:
                    log.info(f"Transmisted peers: {', '.join(short_list)}")
                    return True
        except Exception as e:  # ClientConnectorError
            log.error(f"Error transmitting peers: {e}")

        return False

    @formalin(message="Gathering peers", sleep=30)
    @connectguard
    async def gather_peers(self, quality: float = 1.0):
        """
        Long-running task that continously updates the set of peers connected to this
        node.
        :param quality:
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        found_peers = await self.api.peers(param="peerId", quality=quality)

        if found_peers:
            new_peers = set(found_peers) - set(self.peers)
            vanished_peers = set(self.peers) - set(found_peers)

            for peer in new_peers:
                self.peers.add(peer)
                log.info(f"Found new peer {peer[-5:]}")

            for peer in vanished_peers:
                log.info(f"Peer {peer[-5:]} vanished")

    @formalin(message="MOCK Gathering peers", sleep=10)
    async def mock_gather_peers(self, quality: float = 1.0):
        """
        MOCKING - Long-running task that continously updates the set of peers connected
        to this node.
        :param quality:
        :returns: nothing; the set of connected peerIds is kept in self.peers.
        """

        number_to_pick = random.randint(5, 10)
        found_peers = random.sample(self.all_peers, number_to_pick)

        if found_peers:
            new_peers = set(found_peers) - set(self.peers)
            vanished_peers = set(self.peers) - set(found_peers)

            for peer in new_peers:
                self.peers.add(peer)
                log.info(f"Found new peer {peer}")

            for peer in vanished_peers:
                log.info(f"Peer {peer} vanished")

    @formalin(message="Pinging peers", sleep=20.0)
    @connectguard
    async def ping_peers(self):
        """
        Pings the peers of this node and records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a list of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.
        """

        # shuffle the peer set to converge towards a uniform distribution of pings among
        # peers
        sampled_peers = random.sample(sorted(self.peers), len(self.peers))

        # create an array to keep the latency measures of new peers
        for peer_id in sampled_peers:
            if peer_id not in self.latency:
                self.latency[peer_id] = []

        for peer_id in sampled_peers:
            if not self.connected:
                break
            else:
                await asyncio.sleep(0.1)
            # Above delay is set to allow the second peer's pinging from the test file
            # before timeout (defined by test method). Can be changed.

            latency = await self.api.ping(peer_id, "latency")

            self.latency[peer_id].append(latency)
            self.latency[peer_id] = self.latency[peer_id][-self.max_lat_count :]

    @formalin(message="MOCK Pinging peers", sleep=60.0)
    async def mock_ping_peers(self):
        """
        MOCKING - Pings the peers of this node and records latency measures.

        The recorded latency measures are kept in the dictionary `self.latency`,
        where each peer ID is associated with a list of latency values.
        Only the most recent `self.max_lat_count` latency measures are stored
        for each peer.
        """

        sampled_peers = random.sample(sorted(self.peers), len(self.peers))

        # create an array to keep the latency measures of new peers
        for peer_id in sampled_peers:
            if peer_id not in self.latency:
                self.latency[peer_id] = []

        for peer_id in sampled_peers:
            # Above delay is set to allow the second peer's pinging from the test file
            # before timeout (defined by test method). Can be changed.

            latency = random.randint(10, 100) if random.random() < 0.8 else None

            self.latency[peer_id].append(latency)
            self.latency[peer_id] = self.latency[peer_id][-self.max_lat_count :]

    @wakeupcall(message="Initiated peers transmission", seconds=60)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        async with ClientSession() as session:
            success = await self._post_list(session, self.peers, self.latency)

            if not success:
                asyncio.sleep(5)
                await self._post_list(session, self.peers, self.latency)

        self.wipe_peers()

    @formalin(message="MOCK Initiated peers transmission", sleep=600)
    async def mock_transmit_peers(self):
        """
        MOCKING - Sends the detected peers to the Aggregator
        """
        async with ClientSession() as session:
            success = await self._post_list(session, self.peers, self.latency)

            if not success:
                asyncio.sleep(5)
                await self._post_list(session, self.peers, self.latency)

        # self.wipe_peers()

    async def start(self):
        """
        Starts the tasks of this node
        """
        log.info(f"Starting instance '{self.id}'")
        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.connect(address="hopr")))
        self.tasks.add(asyncio.create_task(self.gather_peers()))
        self.tasks.add(asyncio.create_task(self.ping_peers()))
        self.tasks.add(asyncio.create_task(self.transmit_peers()))

        await asyncio.gather(*self.tasks)

    async def mock_start(self):
        """
        Mock-starts the tasks of this node
        """
        log.info(f"Starting instance '{self.id}'")
        if self.tasks:
            return

        self.started = True
        self.tasks.add(asyncio.create_task(self.mock_gather_peers()))
        self.tasks.add(asyncio.create_task(self.mock_ping_peers()))
        self.tasks.add(asyncio.create_task(self.mock_transmit_peers()))

        await asyncio.gather(*self.tasks)

    def stop(self):
        """
        Stops the tasks of this instance
        """
        log.debug(f"Stopping instance {self.id}")

        self.started = False
        for task in self.tasks:
            task.cancel()
        self.tasks = set()
