import asyncio
import random
import socket

import pytest
from core.api.protocol import Protocol
from core.api.response_objects import Session
from core.components.messages import MessageFormat
from core.components.peer_session_management import PeerSessionManagement
from core.components.tcpudp_server import TCPUDPServer


# Use dynamic port allocation
def get_free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("packet_size", [20])
@pytest.mark.parametrize("batch_size", [4])
@pytest.mark.parametrize("packet_count", [1000])
async def test_udp_server(packet_size: int, batch_size: int, packet_count: int):
    pytest.skip(
        "FIXME: This test is not working as expected. Always going to pass")
    protocol = Protocol.UDP
    entry_ip = "127.0.0.1"
    target_ip = "localhost"

    server = TCPUDPServer(protocol, packet_size, batch_size)

    peer_sessions = [
        PeerSessionManagement(
            Session(
                {
                    "ip": entry_ip,
                    "port": get_free_port(),
                    "protocol": protocol.value,
                    "target": f"{target_ip}:{server.port}",
                }
            )
        ),
        PeerSessionManagement(
            Session(
                {
                    "ip": entry_ip,
                    "port": get_free_port(),
                    "protocol": protocol.value,
                    "target": f"{target_ip}:{server.port}",
                }
            )
        ),
    ]

    i = packet_count
    message = MessageFormat("foo", packet_size)

    while i > 0:
        peer_session = random.choice(peer_sessions)
        if protocol == Protocol.TCP:
            peer_session.socket.send(message.bytes)
        elif protocol == Protocol.UDP:
            peer_session.socket.sendto(message.bytes, peer_session.address)

        i -= 1

    await asyncio.sleep(1)

    server.stop()
