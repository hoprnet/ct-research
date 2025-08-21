import logging
import os
import random
import sys
import time
from typing import Optional

import click
from dotenv import load_dotenv

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI
from core.api.protocol import Protocol
from core.api.response_objects import Metrics, Session, SessionFailure
from core.components.pattern_matcher import PatternMatcher
from core.components.session_to_socket import SessionToSocket
from scripts.lib.decorators import asynchronous
from scripts.lib.state import State
from scripts.lib.tools import packet_statistics, print_path

logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)

load_dotenv()


class Node:
    def __init__(
        self, host: str, port: int, token: Optional[str] = None, p2p_host: str = "127.0.0.1"
    ):
        self.host = host
        self.port = port
        self.token = token
        self.p2p_host = p2p_host
        self._api: Optional[HoprdAPI] = None
        self._address: Optional[str] = None

    @property
    def host_root(self) -> str:
        if "localhost" in self.host:
            return f"localhost:{self.port}"

        if "127.0.0.1" in self.host:
            return f"127.0.0.1:{self.port}"

        return self.host.split("//")[1].split(".")[0]

    @property
    def address_short(self) -> str:
        return f"{self._address[:6]}..{(self._address)[-4:]}"

    @property
    async def address(self) -> str:
        if self._address is None:
            if addr := await self.api.address():
                self._address = addr.native
            else:
                raise ValueError(f"No address found for the HOP node: {self.host}:{self.port}")
        return self._address

    @property
    async def metrics(self) -> Metrics:
        return await self.api.metrics()

    @property
    def api_host(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def api(self):
        if self._api is None:
            self._api = HoprdAPI(self.api_host, self.token)
        return self._api

    @property
    def p2p_endpoint(self):
        target_url = "ctdapp-{}-node-{}-p2p.ctdapp.{}.hoprnet.link"
        pattern = PatternMatcher(r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)")

        if groups := pattern.search(self.host):
            return target_url.format(*groups)
        else:
            logger.warning("No match found for p2p endpoint, using url")
            return self.host


@click.command()
@click.option("--deployment", type=str, default="green")
@click.option("--environment", type=str, default="staging")
@click.option("--waves", type=int, default=100)
@asynchronous
async def main(deployment: str, environment: str, waves: int):
    if environment == "local":
        nodes: list[Node] = [
            Node(host="http://localhost", port=3003, token="e2e-API-token^^"),
            Node(host="http://127.0.0.1", port=3006),
            Node(host="http://localhost", port=3009, token="e2e-API-token^^"),
            Node(host="http://127.0.0.1", port=3012, token="e2e-API-token^^"),
            Node(host="http://localhost", port=3015, token="e2e-API-token^^"),
            Node(host="http://127.0.0.1", port=3018, token="e2e-API-token^^"),
        ]
    else:
        host_format = os.getenv("HOST_FORMAT")
        token = os.getenv(f"{environment.upper()}_TOKEN")

        if host_format is None or token is None:
            logger.info(
                State.FAILURE, f"HOST_FORMAT or {environment.upper()}_TOKEN not set in .env file"
            )
            return

        nodes: list[Node] = [
            Node(host_format % (deployment, idx, environment), 443, token) for idx in range(1, 6)
        ]

    # path: list[Node] = [nodes[idx] for idx in [0, 2, 3]]
    path = random.sample(nodes, k=3)

    [await hop.address for hop in path]

    # get node infos
    try:
        print_path(
            [hop.host_root for hop in path],
            [hop.address_short for hop in path],
            seps=[" <> ", "    "],
        )
    except ValueError as e:
        print(State.FAILURE, f"Error getting addresses: {e}")
        return

    # get sessions
    sessions: list[Session] = await path[0].api.list_sessions()

    sessions_closed = [await path[0].api.close_session(session) for session in sessions]
    print(State.fromBool(all(sessions_closed)), f"Closed {len(sessions)}/{len(sessions)} sessions")

    sessions: list[Session] = await path[0].api.list_sessions()
    if len(sessions) != 0:
        print(State.FAILURE, f"Sessions not closed: {sessions}")
        return

    # open session
    session = await path[0].api.post_session(
        await path[0].address, await path[1].address, path[0].p2p_host, Protocol.UDP
    )

    match session:
        case Session():
            print(State.SUCCESS, "Session opened")
        case SessionFailure():
            print(State.FAILURE, "No session opened")
            return
        case _:
            print(State.UNKNOWN, f"Unknown type: {type(session)}")
            return

    for key, value in session.as_dict.items():
        print(f"\t{key:10s}: {str(value):10s}")

    # create socket
    socket: SessionToSocket = SessionToSocket(session, path[0].p2p_host, 2)

    # send data through socket
    metrics_before: dict[str, Metrics] = {hop.host_root: await hop.api.metrics() for hop in path}

    send_start_time: float = time.time()
    sent_size = sum([await socket.send(random.randbytes(session.payload)) for _ in range(waves)])
    send_elapsed_time: float = time.time() - send_start_time

    print(
        State.SUCCESS,
        f"Sent {sent_size:3d} bytes in {send_elapsed_time*1000:4.0f}ms",
        f"({sent_size/2**10:.2f} kB - {sent_size//session.payload} HOPR packets),",
    )

    # receive data in socket
    recv_start_time: float = time.time()
    recv_size = await socket.receive(session.payload, 2)
    recv_elapsed_time: float = time.time() - recv_start_time

    metrics_after: dict[str, Metrics] = {hop.host_root: await hop.api.metrics() for hop in path}

    print(
        State.fromBool(sent_size == recv_size),
        f"Recv {recv_size:3d} bytes in {recv_elapsed_time*1000:4.0f}ms",
        f"({recv_size/2**10:.2f} kB - {recv_size//session.payload} HOPR packets)",
    )

    # close session
    match await path[0].api.close_session(session):
        case True:
            print(State.SUCCESS, "Session closed")
        case False:
            print(State.FAILURE, "Session not closed")

    # get the difference between the two packet counts
    packet_statistics(metrics_before, metrics_after, "hopr_packets_count")


if __name__ == "__main__":
    main()
