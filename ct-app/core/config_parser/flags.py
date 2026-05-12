from dataclasses import dataclass

from .base_classes import ExplicitParams, Flag


@dataclass(init=False)
class FlagNodeParams(ExplicitParams):
    outgoing_channels_balances: Flag

    healthcheck: Flag
    retrieve_peers: Flag
    refresh_balances: Flag
    refresh_redeemed: Flag
    relay_messages: Flag
    retrieve_balances: Flag

    observe_message_queue: Flag
    maintain_sessions: Flag


@dataclass(init=False)
class FlagPeerParams(ExplicitParams):
    message_relay_request: Flag


@dataclass(init=False)
class FlagParams(ExplicitParams):
    node: FlagNodeParams
    peer: FlagPeerParams
