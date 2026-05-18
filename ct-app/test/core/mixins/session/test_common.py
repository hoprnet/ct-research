from core.api.response_objects import Session
from core.types.peer import Peer
from core.types.message_format import MessageFormat
from core.node import Node


def test_normalize_destination_handles_none_and_case(session_node: Node):
    assert session_node._normalize_destination(None) == ""
    assert session_node._normalize_destination("AbC") == "abc"


def test_session_matches_destination_is_case_insensitive(session_node: Node):
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9100,
            "protocol": "udp",
            "target": "Peer_A",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )

    assert session_node._session_matches_destination(session, "peer_a")
    assert not session_node._session_matches_destination(session, "peer_b")


def test_session_matches_destination_prefers_requested_destination(session_node: Node):
    session = Session(
        {
            "ip": "127.0.0.1",
            "port": 9100,
            "protocol": "udp",
            "target": "#0",
            "hoprMtu": 1002,
            "surbLen": 395,
        }
    )
    session.requested_destination = "0x3BEE5BDE885C6B046ADA28D3E8C180D20A99195A"

    assert session_node._session_matches_destination(
        session, "0x3bee5bde885c6b046ada28d3e8c180d20a99195a"
    )


def test_select_session_destination_returns_none_without_channel(session_node: Node):
    message = MessageFormat("peer_1", "sender", 500, 1)

    assert session_node._select_session_destination(message, []) is None
    assert session_node._select_session_destination(message, ["peer_2"]) is None


def test_select_session_destination_uses_reachable_candidates_only(session_node: Node):
    relayer = "peer_1"
    exit_peer = "peer_exit"
    message = MessageFormat(relayer, "sender", 500, 1)

    session_node.peers = {relayer: Peer(relayer), exit_peer: Peer(exit_peer)}
    session_node.session_destinations = [relayer, exit_peer, "peer_missing"]

    assert session_node._select_session_destination(message, [relayer]) == exit_peer
