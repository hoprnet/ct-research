import logging
import sys
from typing import Optional

import click
from lib.decorators import asynchronous
from lib.state import State

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Metrics, Session, SessionFailure
from core.components.messages.message_format import MessageFormat
from core.components.session_to_socket import SessionToSocket

logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


class HOP:
    def __init__(self, host: str, port: int, token: str, p2p_host: str = "127.0.0.1"):
        self.host = host
        self.port = port
        self.token = token
        self.p2p_host = p2p_host
        self._api: Optional[HoprdAPI] = None
        self._address: Optional[str] = None

    @property
    async def address(self) -> str:
        if self._address is None:
            if addr := await self.api.address():
                self._address = addr.native
            else:
                raise ValueError("No address found for the HOP node")
        return self._address

    @property
    async def packet_count(self) -> dict:
        return (await self.api.metrics()).hopr_packets_count

    @property
    def api_host(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def api(self):
        if self._api is None:
            self._api = HoprdAPI(self.api_host, self.token)
        return self._api


def packet_statistics(packet_counts_before: dict, packet_counts_after: dict):
    print("Packets statistics:")
    for (address, before), (address, after) in zip(
        packet_counts_before.items(), packet_counts_after.items()
    ):
        print(f"\t..{address[-6:]}")
        for key, value in after.items():
            if key not in before:
                print(f"\t\tKey `{key}` not found in before metrics")
                before[key] = 0

            print(f"\t\t{key}: {int(value - before[key]):+d}")


def print_path(hops: list[str]):
    hops = [f"..{hop[-6:]}" for hop in hops]
    str_len = sum(len(hop) for hop in hops) + (len(hops)) * 3 + 1

    print("/" + "=" * str_len + "\\")
    print("|" + " " * str_len + "|")
    print("| " + " <> ".join(hops) + " |")
    print("|" + " " * str_len + "|")
    print("\\" + "=" * str_len + "/")


@click.command()
@click.option("--num-sending", default=50, help="Number of packets to send in one session")
@click.option(
    "--aggregated-messages",
    default=1,
    help="Number of messages to aggregate in one packet",
)
@asynchronous
async def main(
    num_sending: int,
    aggregated_messages: int,
):
    path = [
        HOP(host="https://ctdapp-green-node-1.ctdapp.staging.hoprnet.link",
            port=443, token="^f9pbS266TlcI2uHnPcBH6ouoYbE8ya8qlEVbKYQlF0fOjvkfQD^",
            p2p_host="ctdapp-green-node-1-p2p.ctdapp.staging.hoprnet.link"),
        HOP(host="https://ctdapp-green-node-2.ctdapp.staging.hoprnet.link",
            port=443, token="^f9pbS266TlcI2uHnPcBH6ouoYbE8ya8qlEVbKYQlF0fOjvkfQD^",
            p2p_host="ctdapp-green-node-2-p2p.ctdapp.staging.hoprnet.link"),
        HOP(host="https://ctdapp-green-node-3.ctdapp.staging.hoprnet.link",
            port=443, token="^f9pbS266TlcI2uHnPcBH6ouoYbE8ya8qlEVbKYQlF0fOjvkfQD^", 
            p2p_host="ctdapp-green-node-3-p2p.ctdapp.staging.hoprnet.link"),
    ]
    # get node infos
    try:
        print_path([await hop.address for hop in path])
    except ValueError as e:
        print(State.FAILURE, f"Error getting addresses: {e}")
        return

    # get sessions
    sessions = await path[0].api.list_sessions()
    for session in sessions:
        await path[0].api.close_session(session)

    sessions = await path[0].api.list_sessions()
    if len(sessions) != 0:
        print(State.FAILURE, f"Sessions not closed: {sessions}")
        return

    # open session
    session = await path[0].api.post_session(
        await path[2].address, await path[1].address, path[0].p2p_host
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

    packet_counts_before = {await hop.address: await hop.packet_count for hop in path}

    # send data through socket
    socket = SessionToSocket(session, path[0].p2p_host, 0.5)
    sent_data = []
    recv_data = []
    for _ in range(num_sending):
        message = MessageFormat(
            await path[1].address, await path[0].address, aggregated_messages * session.payload
        )

        size = socket.send(message.bytes())
        sent_data.append(size)
        if (response := socket.receive(size)) and (recv_size := response[1]):
            recv_data.append(recv_size)

    print(
        State.fromBool(
            len(sent_data) == len(recv_data) and all(sent_data) and all(recv_data),
        ),
        f"Sent {len(sent_data)} messages ({sum(sent_data)} bytes -",
        f"{sum(sent_data)//session.payload} HOPR packets),",
        f"received {len(recv_data)} messages ({sum(recv_data)} bytes -",
        f"{sum(recv_data)//session.payload} HOPR packets)",
    )

    packets_count_after = {await hop.address: await hop.packet_count for hop in path}

    # close session
    if session:
        await path[0].api.close_session(session)

    # get session
    match await path[0].api.list_sessions():
        case []:
            print(State.SUCCESS, "Sessions cleaned-up")
        case _:
            print(State.FAILURE, "Session not closed")

    # get the difference between the two packet counts
    packet_statistics(packet_counts_before, packets_count_after)


if __name__ == "__main__":
    main()
    main()
