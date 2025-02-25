from prometheus_client import Gauge, Histogram

BALANCE = Gauge("ct_balance", "Node balance", ["peer_id", "token"])
CHANNELS = Gauge("ct_channels", "Node channels", ["peer_id", "direction"])
CHANNEL_FUNDS = Gauge("ct_channel_funds", "Total funds in out. channels", ["peer_id"])
CHANNELS_OPS = Gauge("ct_channel_operation", "Channel operation", ["peer_id", "op"])
CHANNEL_STAKE = Gauge("ct_peer_channels_balance", "Balance in outgoing channels", ["peer_id"])
DELAY = Gauge("ct_peer_delay", "Delay between two messages", ["peer_id"])
ELIGIBLE_PEERS = Gauge("ct_eligible_peers", "# of eligible peers for rewards")
HEALTH = Gauge("ct_node_health", "Node health", ["peer_id"])
MESSAGE_COUNT = Gauge(
    "ct_message_count", "messages one should receive / year", [
        "peer_id", "model"]
)
MESSAGES_DELAYS = Histogram("ct_messages_delays", "Messages delays", ["sender", "relayer"], buckets=[
                            0.025, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 2.5])
MESSAGES_STATS = Gauge("ct_messages_stats", "", ["type", "sender", "relayer"])
PEER = Gauge("ct_address_pairs",
             "PeerID / address pairs of node reachable by CT", ["peer_id", "address"])
NFT_HOLDERS = Gauge("ct_nft_holders", "Number of nr-nft holders")
NODES_LINKED_TO_SAFE_COUNT = Gauge("ct_peer_safe_count", 
                                   "Number of nodes linked to the safes", 
                                   ["peer_id", "safe"])
PEER_VERSION = Gauge("ct_peer_version", "Peer version", ["peer_id", "version"])
PEERS_COUNT = Gauge("ct_peers_count", "Node peers", ["peer_id"])
QUEUE_SIZE = Gauge("ct_queue_size", "Size of the message queue")
STAKE = Gauge("ct_peer_stake", "Stake", ["safe", "type"])
SUBGRAPH_CALLS = Gauge("ct_subgraph_calls", "# of subgraph calls", ["slug", "type"])
SUBGRAPH_SIZE = Gauge("ct_subgraph_size", "Size of the subgraph")
SUBGRAPH_IN_USE = Gauge("ct_subgraph_in_use", "Subgraph in use", ["slug"])
TICKET_STATS = Gauge("ct_ticket_stats", "Ticket stats", ["type"])
TOPOLOGY_SIZE = Gauge("ct_topology_size", "Size of the topology")
TOTAL_FUNDING = Gauge("ct_total_funding", "Total funding")
UNIQUE_PEERS = Gauge("ct_unique_peers", "Unique peers", ["type"])
