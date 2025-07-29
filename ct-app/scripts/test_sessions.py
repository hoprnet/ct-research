import logging
import random
import sys
import time
from typing import Optional

import click

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI
from core.api.protocol import Protocol
from core.api.response_objects import Metrics, Session, SessionFailure
from core.components.messages.message_format import MessageFormat
from core.components.session_to_socket import SessionToSocket
from scripts.lib.decorators import asynchronous
from scripts.lib.state import State
from scripts.lib.tools import packet_statistics, print_path

logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


class Node:
    def __init__(self, host: str, port: int, token: str, p2p_host: str = "127.0.0.1"):
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
        return f"...{(self._address)[-6:]}"

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


async def only_send(
    socket: SessionToSocket, path: list[Node], message_size: int, loops: int
) -> tuple[list[bytes], int]:
    sent_data: list[bytes] = list()

    for _ in range(loops):
        message = MessageFormat(await path[1].address, await path[0].address, message_size)
        sent_data.append(await socket.send(message))
        # await asyncio.sleep(0.001)

    sent_size: int = sum(len(data) for data in sent_data)
    return sent_data, sent_size


@click.command()
@click.option("--waves", default=100, help="Number of batches to send")
@click.option("--batch-size", default=1, help="Aggregated messages")
@click.option("--timeout", default=1, help="Socket timeout")
@click.option("--local", is_flag=True, help="Use local nodes instead of staging")
@asynchronous
async def main(waves: int, batch_size: int, timeout: int, local: bool):
    if not local:
        nodes = [
            Node(
                host=f"https://ctdapp-green-node-{idx}.ctdapp.staging.hoprnet.link",
                port=443,
                token="^f9pbS266TlcI2uHnPcBH6ouoYbE8ya8qlEVbKYQlF0fOjvkfQD^",
                p2p_host=f"ctdapp-green-node-{idx}-p2p.ctdapp.staging.hoprnet.link",
            )
            for idx in range(1, 6)
        ]
    else:
        nodes = [
            Node(
                host=f"http://localhost",
                port=3003,
                token="e2e-API-token^^",
            ),
            Node(
                host=f"http://127.0.0.1",
                port=3006,
                token="e2e-API-token^^",
            ),
            Node(
                host=f"http://localhost",
                port=3009,
                token="e2e-API-token^^",
            ),
            Node(
                host=f"http://127.0.0.1",
                port=3012,
                token="e2e-API-token^^",
            ),
            Node(
                host=f"http://127.0.0.1",
                port=3018,
                token="e2e-API-token^^",
            )
        ]

    path: list[Node] = random.sample(nodes, k=3)

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
    for session in sessions:
        await path[0].api.close_session(session)

    sessions: list[Session] = await path[0].api.list_sessions()
    if len(sessions) != 0:
        print(State.FAILURE, f"Sessions not closed: {sessions}")
        return

    # open session
    session = await path[0].api.post_session(
        await path[2].address, await path[1].address, path[0].p2p_host, protocol=Protocol.UDP
    )

    match session:
        case Session():
            print(State.SUCCESS, "Session opened")
        case SessionFailure():
            print(State.FAILURE, "No session opened")
            print(session)
            return
        case _:
            print(State.UNKNOWN, f"Unknown type: {type(session)}")
            return

    for key, value in session.as_dict.items():
        print(f"\t{key:10s}: {str(value):10s}")

    # create socket
    socket: SessionToSocket = SessionToSocket(session, path[0].p2p_host, timeout)

    # send data through socket
    metrics_before: dict[str, Metrics] = {hop.host_root: await hop.api.metrics() for hop in path}

    send_start_time: float = time.time()
    sent_data, sent_size = await only_send(socket, path, batch_size * session.payload, waves)
    send_elapsed_time: float = time.time() - send_start_time

    print(
        State.SUCCESS,
        f"Sent {len(sent_data)} messages in {send_elapsed_time*1000:4.0f}ms",
        f"({sent_size/2**10:.2f} kB - {sent_size//session.payload} HOPR packets),",
    )

    # receive data in socket
    recv_start_time: float = time.time()
    recv_data, recv_size = await socket.receive(session.payload, 5)
    recv_elapsed_time: float = time.time() - recv_start_time

    metrics_after: dict[str, Metrics] = {hop.host_root: await hop.api.metrics() for hop in path}

    print(
        State.fromBool(sent_size == recv_size),
        f"Recv {len(recv_data)} messages in {recv_elapsed_time*1000:4.0f}ms",
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
