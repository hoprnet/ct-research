import asyncio
import logging
import os
import re
import sys
from random import randint

from dotenv import load_dotenv
from lib.state import State

sys.path.insert(1, "./")

from core.api.hoprd_api import HoprdAPI
from core.api.response_objects import Session, SessionFailure
from core.components.messages.message_format import MessageFormat
from core.components.session_to_socket import SessionToSocket

load_dotenv()

PACKET_SIZE = 462
NUM_SENDING = 1
AGGREGATED_MESSAGES = 3

logger = logging.getLogger("core.api.hoprd_api")
logger.setLevel(logging.INFO)


async def main(relayer: str = "12D3KooWPq6mC6uewNRANc4YRcigkP1bEUKUFkLX2fBB6deP32Z7"):
    """
    Performs an end-to-end test of session management and message transmission using HoprdAPI.
    
    Establishes a connection to a HOPR node, closes any existing sessions, opens a new session with a specified relayer, sends and receives test messages over a socket, and verifies session cleanup. Prints the outcome of each step to indicate success or failure.
    """
    host = os.getenv("HOST_FORMAT") % ("green", randint(1, 5), "staging")
    token = os.getenv("TOKEN")

    pattern = r"ctdapp-([a-zA-Z]+)-node-(\d+)\.ctdapp\.([a-zA-Z]+)\."
    if match := re.search(pattern, host):
        deployment, index, environment = match.groups()
        p2p_host = f"ctdapp-{deployment}-node-{index}-p2p.ctdapp.{environment}.hoprnet.link"
    else:
        p2p_host = host

    api = HoprdAPI(host, token)

    # get node infos
    print(f"From node: {host}")
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
    session = await api.post_session(own_addresses.hopr, relayer, p2p_host)
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

    # send data through socket
    socket = SessionToSocket(session, p2p_host, 0.1)
    for _ in range(NUM_SENDING):
        message = MessageFormat(AGGREGATED_MESSAGES * PACKET_SIZE, relayer, 1, 1, 1)
        message.sender = own_addresses.hopr

        size = socket.send(message.bytes())
        print(
            State.SUCCESS,
            f"Sent message\n\t {size} bytes, {size / PACKET_SIZE:.1f} HOPR packets",
        )
        if (
            (response := socket.receive(size))
            and (data := response[0])
            and (recv_size := response[1])
        ):
            received = MessageFormat.parse(data)
            print(
                State.fromBool(received == message),
                f"Received message\n\t{recv_size} bytes, {recv_size / PACKET_SIZE:.1f} packets",
            )
        else:
            print(State.FAILURE, "No message received")

    # close session
    if session:
        await api.close_session(session)

    # get session
    session = await api.get_sessions()
    match len(session):
        case 0:
            print(State.SUCCESS, "Sessions cleaned-up")
        case _:
            print(State.FAILURE, "Session not closed")


if __name__ == "__main__":
    asyncio.run(main())
