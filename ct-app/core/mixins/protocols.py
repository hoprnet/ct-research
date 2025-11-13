from datetime import datetime
from typing import Optional, Protocol

from ..api.hoprd_api import HoprdAPI
from ..api.response_objects import Channels, Session
from ..components.address import Address
from ..components.balance import Balance
from ..components.config_parser.parameters import Parameters
from ..components.peer import Peer
from ..components.session_rate_limiter import SessionRateLimiter
from ..rpc.entries import Allocation, ExternalBalance
from ..subgraph import GraphQLProvider, Type
from ..subgraph.entries import Node


class HasAPI(Protocol):
    api: HoprdAPI
    address: Address
    url: str


class HasChannels(Protocol):
    channels: Optional[Channels]
    topology_data: dict[str, Balance]


class HasNFT(Protocol):
    nft_holders_data: list[str]


class HasParams(Protocol):
    params: Parameters


class HasPeers(Protocol):
    peers: set[Peer]
    peer_history: dict[str, datetime]


class HasSession(Protocol):
    session_destinations: list[str]
    sessions: dict[str, Session]
    session_close_grace_period: dict[str, float]  # Tracks grace period start times
    session_rate_limiter: SessionRateLimiter


class HasRPCs(Protocol):
    allocations_data: list[Allocation]
    eoa_balances_data: list[ExternalBalance]


class HasSubgraphs(Protocol):
    graphql_providers: dict[Type, GraphQLProvider]
    peers_rewards_data: dict[str, float]
    registered_nodes_data: list[Node]
