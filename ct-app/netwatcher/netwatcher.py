import asyncio
import random
import time

from aiohttp import ClientSession
from tools import getlogger
from tools.decorator import connectguard, formalin
from tools.hopr_node import HOPRNode

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
        self.peer_id = "<mock-peer-id>"

    def wipe_peers(self):
        """
        Wipes the list of peers
        """
        log.info("Wiping peers")

        self.peers.clear()
        self.latency.clear()

    async def _post_list(self, session: ClientSession, latencies: dict[str, int]):
        """
        Sends the detected peers to the Aggregator. For the moment, only the last
        latency is transmitted for each peer.
        :param session: the aiohttp session
        :param peers: the list of peers
        :param latencies: the list of latencies
        """

        # list standard peer ids (creating a secure copy of the list)
        data = {"id": self.peer_id, "list": latencies}
        peers = list(latencies.keys())

        try:
            async with session.post(self.posturl, json=data) as response:
                if response.status == 200:
                    log.info(f"Transmitted {len(peers)} peers: {', '.join(peers)}")
                    return True
        except Exception:  # ClientConnectorError
            log.exception("Error transmitting peers")

        return False

    async def _post_balance(self, session: ClientSession, balance: int):
        """
        Sends the node balance (xDai) to the Aggregator.
        :param session: the aiohttp session
        :param balance: the node balance
        """
        data = {"id": self.peer_id, "balances": {"native": balance}}
        try:
            async with session.post(self.balanceurl, json=data) as response:
                if response.status == 200:
                    for key, value in data["balances"].items():
                        log.info(f"Transmitted {key} balance: {value}")
                    return True
                log.error(f"{response}")
        except Exception:  # ClientConnectorError
            log.exception("Error transmitting balance")

        return False

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
        # vanished_peers = set(self.peers) - set(found_peers)

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

        # shuffle the peer set to converge towards a uniform distribution of pings among
        # peers
        rand_peer = random.choice(self.peers)

        # # create an array to keep the latency measures of new peers
        # for peer_id in sampled_peers:
        #     if peer_id not in self.latency:
        #         self.latency[peer_id] = []

        # for peer_id in sampled_peers:
        # if not self.connected:
        #     break

        # await asyncio.sleep(0.1)
        # Above delay is set to allow the second peer's pinging from the test file
        # before timeout (defined by test method). Can be changed.

        if self.mock_mode:
            latency = random.randint(10, 100) if random.random() < 0.8 else 0
        else:
            latency = await self.api.ping(rand_peer, "latency")

        if latency is not None:
            self.latency[rand_peer] = latency

        # self.latency[rand_peer] = self.latency[rand_peer][-self.max_lat_count :]

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

        async with ClientSession() as session:
            success = await self._post_list(session, peers_to_send)

            if not success:
                asyncio.sleep(5)
                success = await self._post_list(session, peers_to_send)

        if not success:
            return

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

        async with ClientSession() as session:
            success = await self._post_balance(session, balance)

            if success:
                return

            await asyncio.sleep(5)
            await self._post_balance(session, balance)

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
