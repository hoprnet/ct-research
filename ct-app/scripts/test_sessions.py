import asyncio
import logging
import sys

import click
from lib.decorators import asynchronous
from lib.state import State

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Session, SessionFailure
from core.components.messages.message_format import MessageFormat
from core.components.session_to_socket import SessionToSocket

logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


def get_packet_counts_from_metrics(metrics: str) -> dict:
    """
    Extract packet counts from metrics string.
    """
    if metrics is None:
        return {}

    hopr_packet_counts = [
        line
        for line in metrics.split("\n")
        if "hopr_packets_count" in line and not line.startswith("#")
    ]
    packet_counts = {}
    for line in hopr_packet_counts:
        key, value = line.split(" ")
        packet_counts[key.split('"')[1]] = int(value)
    return packet_counts


@click.command()
@click.option(
    "--relayer",
    default="12D3KooWPq6mC6uewNRANc4YRcigkP1bEUKUFkLX2fBB6deP32Z7",
    help="Relayer address",
)
@click.option("--packet-size", default=810, help="Packet size")
@click.option("--num-sending", default=10, help="Number of packets to send in one session")
@click.option(
    "--aggregated-messages",
    default=1,
    help="Number of messages to aggregate in one packet",
)
@click.option(
    "--sleep-time",
    default=5,
    help="Time to sleep before closing the session",
)
@asynchronous
async def main(
    relayer: str,
    packet_size: int,
    num_sending: int,
    aggregated_messages: int,
    sleep_time: int,
):
    host = "http://localhost"
    p2p_host = "127.0.0.1"

    api_port = 3003
    token = "e2e-API-token^^"

    api_host = f"{host}:{api_port}"

    api = HoprdAPI(api_host, token)

    # get node infos
    print(f"From node: {api_host}")
    own_addresses = await api.get_address()
    if own_addresses is None:
        print(State.FAILURE, "No addresses found")
        return

    # get sessions
    sessions = await api.get_sessions()
    for session in sessions:
        await api.close_session(session)

    sessions = await api.get_sessions()
    if len(sessions) != 0:
        print(State.FAILURE, f"Sessions not closed: {sessions}")
        return

    # open session
    session = await api.post_session(own_addresses.native, relayer, p2p_host)
    for key, value in session.as_dict.items():
        print(f"\t{key:10s}: {value:10s}")

    match session:
        case Session():
            print(State.SUCCESS, "Session opened")
        case SessionFailure():
            print(State.FAILURE, "No session opened")
            return
        case _:
            print(State.UNKNOWN, f"Unknown type: {type(session)}")
            return

    packets_count_before = get_packet_counts_from_metrics(await api.metrics())

    # send data through socket
    socket = SessionToSocket(session, p2p_host, 1)
    sent_data = []
    recv_data = []
    for _ in range(num_sending):
        message = MessageFormat(aggregated_messages * packet_size, relayer, "", 1, 1, 1)
        message.sender = own_addresses.native

        size = socket.send(message.bytes())
        sent_data.append(size)
        if (response := socket.receive(size)) and (recv_size := response[1]):
            recv_data.append(recv_size)

    print(
        State.fromBool(
            len(sent_data) == len(recv_data) and all(sent_data) and all(recv_data),
        ),
        f"Sent {len(sent_data)} messages ({sum(sent_data)} bytes -",
        f"{sum(sent_data)//packet_size} HOPR packets),",
        f"received {len(recv_data)} messages ({sum(recv_data)} bytes -",
        f"{sum(recv_data)//packet_size} HOPR packets)",
    )

    packets_count_after = get_packet_counts_from_metrics(await api.metrics())

    # close session
    if session:
        print(State.UNKNOWN, f"Sleep for {sleep_time} seconds before closing the session")
        await asyncio.sleep(sleep_time)
        await api.close_session(session)

    # get session
    session = await api.get_sessions()
    match len(session):
        case 0:
            print(State.SUCCESS, "Sessions cleaned-up")
        case _:
            print(State.FAILURE, "Session not closed")

    # get the difference between the two packet counts
    print("Packets statistics:")
    for key, value in packets_count_after.items():
        if key not in packets_count_before:
            print(f"\tKey {key} not found in before metrics")
            packets_count_before[key] = 0
            # continue

        print(f"\t{key}: {value - packets_count_before[key]}")


if __name__ == "__main__":
    asyncio.run(main())
