import asyncio
from copy import deepcopy
import random
import time

from tools.decorator import connectguard, formalin
from tools.hopr_node import HOPRNode
from tools.utils import getlogger, post_dictionary, envvar
from .latency_measure import LatencyMeasure
from .peer import Peer

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
        self.peers = list[Peer]()

        # a dict to keep the max_lat_count latency measures along with the timestamp
        self.measures = dict[str, LatencyMeasure]()
        self.last_peer_transmission: float = 0

        self.max_lat_count = max_lat_count

        self.measures_lock = asyncio.Lock()

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

        self.peers = [
            Peer(peer["peer_id"], peer["peer_address"]) for peer in found_peers
        ]
        _short_peers = [".." + peer.short_id for peer in self.peers]

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

        if envvar("MOCK_LATENCY", int):
            latency = random.randint(0, 100)
        else:
            latency = await self.api.ping(rand_peer.id, "latency")
            log.debug(f"Measured latency to {rand_peer.id[-5:]}: {latency}ms")

        # latency update rule is:
        # - if latency measure fails:
        #     - if the peer is not known, add it with value -1 and set timestamp
        #     - if the peer is known and the last measure is recent, do nothing
        # - if latency measure succeeds, always update

        now = time.time()
        async with self.measures_lock:
            if latency != 0:
                self.measures[rand_peer.id] = LatencyMeasure(
                    latency, now, rand_peer, True
                )

                return

            log.warning(f"Failed to ping {rand_peer.id}")

            if (
                rand_peer.id not in self.measures
                or self.measures[rand_peer.id].value is None
            ):
                log.debug(f"Adding {rand_peer.id} to latency dictionary with value -1")

                self.measures[rand_peer.id] = LatencyMeasure(-1, now, rand_peer, True)
                return

            log.debug(f"Keeping {rand_peer.id} in latency dictionary (recent measure)")

    @formalin(message="Initiated peers transmission", sleep=20)
    @connectguard
    async def transmit_peers(self):
        """
        Sends the detected peers to the Aggregator
        """
        measures_to_send: list[LatencyMeasure] = []

        # access the peers address in the latency dictionary in a thread-safe way
        async with self.measures_lock:
            local_measures = deepcopy(self.measures)

        # convert the latency dictionary to a simpler dictionary for the aggregator
        for measure in local_measures.values():
            if not measure.transmit:
                continue
            measures_to_send.append(measure)

        # pick randomly `self.max_lat_count` peers from peer values
        selected_measures = random.sample(
            measures_to_send, k=min(self.max_lat_count, len(measures_to_send))
        )

        # checks if transmission needs to be triggered by peer-list size
        if len(selected_measures) == self.max_lat_count:
            log.info("Peers transmission triggered by latency dictionary size")
        # checks if transmission needs to be triggered by timestamp
        elif (
            time.time() - self.last_peer_transmission > 60 * 5
            and len(selected_measures) != 0
        ):  # 5 minutes
            log.info("Peers transmission triggered by timestamp")
        else:
            log.info(
                f"Peer transmission skipped. {len(selected_measures)} peers waiting"
            )
            return

        data = {
            "id": self.peer_id,
            "peers": {measure.node.id: measure.value for measure in selected_measures},
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

        log.info(
            f"Transmitted {len(selected_measures)} peers: "
            + f"{', '.join([m.short_id for m in selected_measures])}"
        )

        # reset the transmitted key-value pair from self.latency in a
        # thread-safe way
        async with self.measures_lock:
            self.last_peer_transmission = time.time()
            for measure in selected_measures:
                self.measures[measure.node.id].value = None
                self.measures[measure.node.id].transmit = False

    @formalin(message="Sending node balance", sleep=60 * 5)
    @connectguard
    async def transmit_balance(self):
        balances = await self.api.balances(["native", "hopr"])

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

    @formalin(message="Handling channels to peers", sleep=5 * 60 + 5)
    @connectguard
    async def handle_channels(self):
        """
        Open channels to peers that have been successfully pinged at least once.
        """
        async with self.measures_lock:
            local_measures: dict[str, LatencyMeasure] = deepcopy(self.measures)

        # Getting all channels
        all_channels = await self.api.all_channels(False)

        # Filtering outgoing channels
        outgoing_channels = [
            c for c in all_channels.all if c.source_peer_id == self.peer_id
        ]

        # Peer addresses of peer not connected for more than 1 day
        not_connected_nodes = [
            m.node.address for m in local_measures.values() if m.close_channel
        ]
        not_connected_nodes_channels = [
            c for c in outgoing_channels if c.destination_address in not_connected_nodes
        ]

        # Filtering outgoing channel with status "Open" and "PendingToClose", and low
        # balance channels
        open_channels = [c for c in outgoing_channels if c.status == "Open"]
        pending_to_close_channels = [
            c for c in outgoing_channels if c.status == "PendingToClose"
        ]
        low_balance_channels = [
            c
            for c in open_channels
            if int(c.balance) / 1e18 <= envvar("MINIMUM_BALANCE_IN_CHANNEL", float)
        ]

        # Peer addresses behind the outgoing opened channels
        peer_address_behind_open_channels = {
            c.destination_address for c in open_channels
        }
        peer_addresses = set([m.node.address for m in local_measures.values()])

        addresses_without_out_channel = (
            peer_addresses - peer_address_behind_open_channels
        )

        #### CLOSE PENDING TO CLOSE CHANNELS ####
        for channel in pending_to_close_channels:
            log.info(
                f"Closing channel to {channel.channel_id} (was in PendingToClose state)"
            )
            success = await self.api.close_channel(channel.channel_id)
            log.info(f"Channel {channel.channel_id} closed: {success}")

        #### CLOSE CHANNELS TO PEERS NOT CONNECTED PEERS ####
        for channel in not_connected_nodes_channels:
            log.info(
                f"Closing channel to {channel.channel_id} "
                + "(peer not connected for a long time)"
            )
            success = await self.api.close_channel(channel.channel_id)
            log.info(f"Channel {channel.channel_id} closed: {success}")

        #### FUND LOW BALANCE CHANNELS ####
        for channel in low_balance_channels:
            balance = int(channel.balance) / 1e18
            log.info(
                f"Re-funding channel {channel.channel_id} (balance: {balance} < "
                + f"{envvar('MINIMUM_BALANCE_IN_CHANNEL')})"
            )
            sucess = await self.api.fund_channel(
                channel.channel_id, envvar("CHANNEL_INITIAL_BALANCE")
            )
            log.info(f"Channel {channel.channel_id} funded: {sucess}")

        #### OPEN NEW CHANNELS ####
        for address in addresses_without_out_channel:
            log.info(f"Opening channel to {address}")
            success = await self.api.open_channel(
                address, envvar("CHANNEL_INITIAL_BALANCE")
            )
            log.info(f"Channel to {address} opened: {success}")

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
        self.tasks.add(asyncio.create_task(self.handle_channels()))
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
