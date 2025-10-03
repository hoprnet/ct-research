from dataclasses import dataclass

from .base_classes import ExplicitParams, Flag


@dataclass(init=False)
class FlagNodeParams(ExplicitParams):
    apply_economic_model: Flag
    ticket_parameters: Flag

    outgoing_channels_balances: Flag
    rotate_subgraphs: Flag
    peers_rewards: Flag
    registered_nodes: Flag
    allocations: Flag
    eoa_balances: Flag

    healthcheck: Flag
    retrieve_peers: Flag
    retrieve_channels: Flag
    retrieve_balances: Flag
    open_channels: Flag
    fund_channels: Flag
    close_old_channels: Flag
    close_pending_channels: Flag
    close_incoming_channels: Flag
    get_total_channel_funds: Flag

    observe_message_queue: Flag
    maintain_sessions: Flag


@dataclass(init=False)
class FlagPeerParams(ExplicitParams):
    message_relay_request: Flag


@dataclass(init=False)
class FlagParams(ExplicitParams):
    node: FlagNodeParams
    peer: FlagPeerParams
