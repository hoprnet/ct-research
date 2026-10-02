from dataclasses import dataclass

from .base_classes import ExplicitParams, Flag


@dataclass(init=False, repr=False)
class FlagNodeParams(ExplicitParams):

    healthcheck: Flag
    retrieve_peers: Flag
    relay_messages: Flag
    retrieve_balances: Flag

    observe_message_queue: Flag
    maintain_sessions: Flag


@dataclass(init=False, repr=False)
class FlagParams(ExplicitParams):
    node: FlagNodeParams
