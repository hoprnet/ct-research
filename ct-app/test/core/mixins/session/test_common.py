from core.types.peer import Peer
from core.types.message_format import MessageFormat
from core.node import Node


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
